// loadgen 是实验 2 的压测工具：按给定的到达率（每秒请求数）分阶段施加负载，开环，
// 每个阶段输出一行客户端看到的吞吐、错误率和延迟分布。
//
// 开环的意思是：请求按计划的时刻发出，不管前面的请求有没有返回。服务变慢时请求照样到达、在服务里排队，
// 这和真实用户的行为一致。wrk 这类闭环工具（固定 N 个连接，收到响应才发下一个）在服务变慢时会自动少发，
// 看到的延迟偏乐观。
//
// 口径（指导书第 3 节）：
//   - 阶段：按“计划发送时刻”把请求归到阶段，阶段之间不留空隙。
//   - 吞吐 ok_rps：该阶段成功（2xx）的请求数 ÷ 阶段时长。
//   - 错误率 error_rate：（非 2xx + 超时 + 连接错误）÷ 实际发出的请求数。
//   - 延迟：只统计成功的请求，从“计划发送时刻”到读完响应体为止；分位数用最近秩法（排序后第 ceil(p% × n) 个）。
//     从计划时刻算起，压测机自己发晚了的时间也会算进去，所以要同时看 lag_p99_ms（发送滞后）。
//   - slo_good：成功且延迟不超过 -slo 的请求 ÷ 实际发出的请求数（客户端视角的 SLI）。
//   - gen_cpu_pct：压测机进程自己用掉的 CPU，100 表示一个核；用来检查压测机有没有成为瓶颈。
package main

import (
	"context"
	"encoding/csv"
	"errors"
	"flag"
	"fmt"
	"io"
	"math"
	"math/rand/v2"
	"net"
	"net/http"
	"os"
	"runtime"
	"slices"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"syscall"
	"time"
)

type options struct {
	url, method, body string
	rates             []float64
	step, timeout     time.Duration
	slo               time.Duration
	poisson           bool
	maxInflight       int64
	seed              uint64
	stopBelow         float64
}

// stepStats 累计一个阶段里的结果。
type stepStats struct {
	mu                                sync.Mutex
	sent, ok, httpErr, timeout, other int
	dropped                           int
	good                              int
	lat, lag                          []float64 // 毫秒
	codes                             map[int]int
}

func (s *stepStats) add(kind resultKind, code int, lat, lag time.Duration, slo time.Duration) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.lag = append(s.lag, ms(lag))
	switch kind {
	case resOK:
		s.ok++
		s.lat = append(s.lat, ms(lat))
		if lat <= slo {
			s.good++
		}
	case resHTTP:
		s.httpErr++
		if s.codes == nil {
			s.codes = map[int]int{}
		}
		s.codes[code]++
	case resTimeout:
		s.timeout++
	default:
		s.other++
	}
}

type resultKind int

const (
	resOK resultKind = iota
	resHTTP
	resTimeout
	resOther
)

func ms(d time.Duration) float64 { return float64(d) / float64(time.Millisecond) }

func main() {
	if os.Getenv("O4_BEARER_TOKEN") == "" {
		fmt.Fprintln(os.Stderr, "O4_BEARER_TOKEN is required")
		os.Exit(2)
	}
	var o options
	var rates, arrival string
	flag.StringVar(&o.url, "url", "", "目标地址，例如 http://127.0.0.1:8080/api/courses/1")
	flag.StringVar(&o.method, "method", "", "HTTP 方法；默认 GET，给了 -body 时默认 POST")
	flag.StringVar(&o.body, "body", "", `请求体模板，{{seq}} 换成请求序号，例如 '{"student":"s{{seq}}","course":"c1"}'`)
	flag.StringVar(&rates, "rates", "", "各阶段的目标到达率（请求/秒），逗号分隔；0 表示这一阶段不发请求（空载基线）")
	flag.DurationVar(&o.step, "step", 30*time.Second, "每个阶段的时长")
	flag.DurationVar(&o.timeout, "timeout", 2*time.Second, "单个请求的超时（含建连）")
	flag.DurationVar(&o.slo, "slo", 50*time.Millisecond, "计算 slo_good 用的延迟阈值")
	flag.StringVar(&arrival, "arrival", "poisson", "到达过程：poisson（间隔服从指数分布，模拟彼此独立的用户）或 uniform（等间隔）")
	flag.Int64Var(&o.maxInflight, "max-inflight", 20000, "在途请求上限；超过时这次请求不发，记为 dropped，说明压测机或服务已经严重过载")
	flag.Uint64Var(&o.seed, "seed", 1, "随机种子")
	flag.Float64Var(&o.stopBelow, "stop-below", 0.5, "某个阶段结束时，已成功返回的请求不到已发出的这个比例，就不再进行后面的阶段（服务已经崩了，再加压只会拖垮主机）；0 表示不停")
	out := flag.String("out", "", "把结果写成 CSV 文件（同时仍在终端打印表格）")
	flag.Parse()

	var err error
	if o.rates, err = parseRates(rates); err != nil || o.url == "" {
		fmt.Fprintln(os.Stderr, "用法：loadgen -url URL -rates 100,200,400 [-step 30s] [-body 模板] [-out steps.csv]")
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
		}
		os.Exit(2)
	}
	switch arrival {
	case "poisson":
		o.poisson = true
	case "uniform":
	default:
		fmt.Fprintln(os.Stderr, "-arrival 只能是 poisson 或 uniform")
		os.Exit(2)
	}
	if o.method == "" {
		o.method = "GET"
		if o.body != "" {
			o.method = "POST"
		}
	}

	fmt.Fprintf(os.Stderr, "loadgen：%s %s，%d 个阶段 × %v，到达过程 %s，超时 %v，GOMAXPROCS=%d\n",
		o.method, o.url, len(o.rates), o.step, arrival, o.timeout, runtime.GOMAXPROCS(0))
	rows := run(o, os.Stderr)
	printTable(os.Stdout, rows)
	if *out != "" {
		f, err := os.Create(*out)
		if err == nil {
			err = writeCSV(f, rows)
			if cerr := f.Close(); err == nil {
				err = cerr
			}
		}
		if err != nil {
			fmt.Fprintln(os.Stderr, "写 CSV 失败：", err)
			os.Exit(1)
		}
	}
}

func parseRates(s string) ([]float64, error) {
	if s == "" {
		return nil, errors.New("缺少 -rates")
	}
	var rs []float64
	for _, f := range strings.Split(s, ",") {
		r, err := strconv.ParseFloat(strings.TrimSpace(f), 64)
		if err != nil || r < 0 || math.IsInf(r, 0) || math.IsNaN(r) {
			return nil, fmt.Errorf("到达率 %q 不合法", f)
		}
		rs = append(rs, r)
	}
	return rs, nil
}

func newClient(o options) *http.Client {
	tr := &http.Transport{
		// 不限制连接数：连接数一旦封顶，请求会在客户端里排队，测到的就不是服务的延迟了。
		MaxIdleConns:        0,
		MaxIdleConnsPerHost: int(o.maxInflight),
		MaxConnsPerHost:     0,
		IdleConnTimeout:     90 * time.Second,
		DisableCompression:  true,
		DialContext:         (&net.Dialer{Timeout: o.timeout, KeepAlive: 30 * time.Second}).DialContext,
	}
	return &http.Client{Transport: tr, Timeout: o.timeout}
}

type row struct {
	name              string
	target            float64
	start, end        time.Time
	sent, ok          int
	httpErr, timeout  int
	other, dropped    int
	okRPS, errRate    float64
	mean, p50, p90    float64
	p99, max          float64
	good, lagP99, cpu float64
	codes             map[int]int
	warn              []string
}

func run(o options, log io.Writer) []row {
	client := newClient(o)
	rng := rand.New(rand.NewPCG(o.seed, 0x5eed))
	stats := make([]*stepStats, len(o.rates))
	starts := make([]time.Time, len(o.rates))
	cpus := make([]float64, len(o.rates))
	var inflight atomic.Int64
	var wg sync.WaitGroup
	var seq int64

	begin := time.Now()
	for i, rate := range o.rates {
		st := &stepStats{}
		stats[i] = st
		stepStart := begin.Add(time.Duration(i) * o.step)
		stepEnd := stepStart.Add(o.step)
		starts[i] = stepStart
		cpu0 := cpuSeconds()
		if rate > 0 {
			next := stepStart
			for {
				gap := 1 / rate
				if o.poisson {
					gap = rng.ExpFloat64() / rate
				}
				next = next.Add(time.Duration(gap * float64(time.Second)))
				if !next.Before(stepEnd) {
					break
				}
				if d := time.Until(next); d > 0 {
					time.Sleep(d)
				}
				seq++
				if inflight.Load() >= o.maxInflight {
					st.mu.Lock()
					st.dropped++
					st.mu.Unlock()
					continue
				}
				st.mu.Lock()
				st.sent++
				st.mu.Unlock()
				inflight.Add(1)
				wg.Add(1)
				go func(intended time.Time, seq int64) {
					defer wg.Done()
					defer inflight.Add(-1)
					kind, code, lat, lag := send(client, o, intended, seq)
					st.add(kind, code, lat, lag, o.slo)
				}(next, seq)
			}
		}
		time.Sleep(time.Until(stepEnd))
		cpus[i] = (cpuSeconds() - cpu0) / o.step.Seconds() * 100
		st.mu.Lock()
		fmt.Fprintf(log, "阶段 %d/%d：目标 %g 请求/秒，已发出 %d，已成功 %d，在途 %d，压测机 CPU %.0f%%\n",
			i+1, len(o.rates), rate, st.sent, st.ok, inflight.Load(), cpus[i])
		collapsed := st.sent > 0 && float64(st.ok) < o.stopBelow*float64(st.sent)
		st.mu.Unlock()
		if collapsed && i < len(o.rates)-1 {
			fmt.Fprintf(log, "这一阶段成功返回的不到 %.0f%%，后面 %d 个阶段不再进行（-stop-below）\n", o.stopBelow*100, len(o.rates)-1-i)
			o.rates = o.rates[:i+1]
			stats, starts, cpus = stats[:i+1], starts[:i+1], cpus[:i+1]
			break
		}
	}
	fmt.Fprintf(log, "等待在途的 %d 个请求结束（最多 %v）…\n", inflight.Load(), o.timeout)
	wg.Wait()

	var rows []row
	all := &stepStats{}
	var allCPU float64
	active := 0
	for i, st := range stats {
		r := summarize(fmt.Sprint(i+1), o.rates[i], starts[i], starts[i].Add(o.step), st, o.step, cpus[i])
		rows = append(rows, r)
		if o.rates[i] > 0 {
			all.merge(st)
			allCPU += cpus[i]
			active++
		}
	}
	if active > 0 {
		r := summarize("all", math.NaN(), starts[0], starts[len(starts)-1].Add(o.step), all,
			time.Duration(active)*o.step, allCPU/float64(active))
		r.warn = nil
		rows = append(rows, r)
	}
	for _, r := range rows {
		for _, w := range r.warn {
			fmt.Fprintf(log, "警告（阶段 %s）：%s\n", r.name, w)
		}
	}
	return rows
}

func send(client *http.Client, o options, intended time.Time, seq int64) (resultKind, int, time.Duration, time.Duration) {
	actual := time.Now()
	lag := actual.Sub(intended)
	var body io.Reader
	if o.body != "" {
		body = strings.NewReader(strings.ReplaceAll(o.body, "{{seq}}", strconv.FormatInt(seq, 10)))
	}
	req, err := http.NewRequestWithContext(context.Background(), o.method, o.url, body)
	if err != nil {
		return resOther, 0, 0, lag
	}
	req.Header.Set("Authorization", "Bearer "+os.Getenv("O4_BEARER_TOKEN"))
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	resp, err := client.Do(req)
	if err == nil {
		_, err = io.Copy(io.Discard, resp.Body)
		resp.Body.Close()
	}
	lat := time.Since(intended)
	switch {
	case err != nil && isTimeout(err):
		return resTimeout, 0, lat, lag
	case err != nil:
		return resOther, 0, lat, lag
	case resp.StatusCode < 200 || resp.StatusCode > 299:
		return resHTTP, resp.StatusCode, lat, lag
	}
	return resOK, resp.StatusCode, lat, lag
}

func isTimeout(err error) bool {
	var ne net.Error
	return errors.Is(err, context.DeadlineExceeded) || (errors.As(err, &ne) && ne.Timeout())
}

func (s *stepStats) merge(o *stepStats) {
	s.sent += o.sent
	s.ok += o.ok
	s.httpErr += o.httpErr
	s.timeout += o.timeout
	s.other += o.other
	s.dropped += o.dropped
	s.good += o.good
	s.lat = append(s.lat, o.lat...)
	s.lag = append(s.lag, o.lag...)
	for c, n := range o.codes {
		if s.codes == nil {
			s.codes = map[int]int{}
		}
		s.codes[c] += n
	}
}

func summarize(name string, target float64, start, end time.Time, st *stepStats, dur time.Duration, cpu float64) row {
	r := row{name: name, target: target, start: start, end: end, sent: st.sent, ok: st.ok, httpErr: st.httpErr,
		timeout: st.timeout, other: st.other, dropped: st.dropped, cpu: cpu, codes: st.codes}
	r.okRPS = float64(st.ok) / dur.Seconds()
	nan := math.NaN()
	r.errRate, r.good, r.mean, r.p50, r.p90, r.p99, r.max, r.lagP99 = nan, nan, nan, nan, nan, nan, nan, nan
	if st.sent > 0 {
		r.errRate = float64(st.httpErr+st.timeout+st.other) / float64(st.sent)
		r.good = float64(st.good) / float64(st.sent)
	}
	if n := len(st.lat); n > 0 {
		slices.Sort(st.lat)
		var sum float64
		for _, v := range st.lat {
			sum += v
		}
		r.mean = sum / float64(n)
		r.p50, r.p90, r.p99 = percentile(st.lat, 50), percentile(st.lat, 90), percentile(st.lat, 99)
		r.max = st.lat[n-1]
	}
	if len(st.lag) > 0 {
		slices.Sort(st.lag)
		r.lagP99 = percentile(st.lag, 99)
	}
	if st.dropped > 0 {
		r.warn = append(r.warn, fmt.Sprintf("%d 个请求因在途数达到 -max-inflight 没有发出", st.dropped))
	}
	if cpu > 0.8*float64(runtime.GOMAXPROCS(0))*100 {
		r.warn = append(r.warn, fmt.Sprintf("压测机 CPU %.0f%%，接近它能用的 %d 个核，压测机可能成了瓶颈", cpu, runtime.GOMAXPROCS(0)))
	}
	if r.lagP99 > 2 && st.sent > 0 {
		r.warn = append(r.warn, fmt.Sprintf("发送滞后 p99 = %.1f ms，压测机没能按计划发出请求", r.lagP99))
	}
	return r
}

// percentile 用最近秩法：已排序的 n 个数里第 ceil(p/100 × n) 个。
func percentile(sorted []float64, p float64) float64 {
	n := len(sorted)
	k := int(math.Ceil(p / 100 * float64(n)))
	return sorted[max(0, min(k-1, n-1))]
}

func cpuSeconds() float64 {
	var ru syscall.Rusage
	if err := syscall.Getrusage(syscall.RUSAGE_SELF, &ru); err != nil {
		return 0
	}
	return float64(ru.Utime.Sec+ru.Stime.Sec) + float64(ru.Utime.Usec+ru.Stime.Usec)/1e6
}

var header = []string{"step", "target_rps", "start_unix", "end_unix", "start_local",
	"sent", "ok", "http_err", "timeout", "net_err", "dropped",
	"ok_rps", "error_rate", "mean_ms", "p50_ms", "p90_ms", "p99_ms", "max_ms",
	"slo_good", "lag_p99_ms", "gen_cpu_pct", "codes", "warn"}

func (r row) fields() []string {
	f := func(v float64, prec int) string {
		if math.IsNaN(v) {
			return ""
		}
		return strconv.FormatFloat(v, 'f', prec, 64)
	}
	var codes []string
	for c, n := range r.codes {
		codes = append(codes, fmt.Sprintf("%d:%d", c, n))
	}
	slices.Sort(codes)
	return []string{r.name, f(r.target, 0), strconv.FormatInt(r.start.Unix(), 10), strconv.FormatInt(r.end.Unix(), 10),
		r.start.Format("15:04:05"),
		strconv.Itoa(r.sent), strconv.Itoa(r.ok), strconv.Itoa(r.httpErr), strconv.Itoa(r.timeout), strconv.Itoa(r.other),
		strconv.Itoa(r.dropped),
		f(r.okRPS, 1), f(r.errRate, 4), f(r.mean, 2), f(r.p50, 2), f(r.p90, 2), f(r.p99, 2), f(r.max, 2),
		f(r.good, 4), f(r.lagP99, 2), f(r.cpu, 0), strings.Join(codes, " "), strings.Join(r.warn, "；")}
}

func writeCSV(w io.Writer, rows []row) error {
	cw := csv.NewWriter(w)
	cw.Write(header)
	for _, r := range rows {
		cw.Write(r.fields())
	}
	cw.Flush()
	return cw.Error()
}

func printTable(w io.Writer, rows []row) {
	cols := []int{0, 1, 5, 6, 12, 13, 14, 16, 17, 18, 19, 20} // 终端里只放主要几列，完整的看 CSV
	table := [][]string{}
	h := make([]string, len(cols))
	for i, c := range cols {
		h[i] = header[c]
	}
	table = append(table, h)
	for _, r := range rows {
		f := r.fields()
		line := make([]string, len(cols))
		for i, c := range cols {
			line[i] = f[c]
		}
		table = append(table, line)
	}
	width := make([]int, len(cols))
	for _, line := range table {
		for i, v := range line {
			width[i] = max(width[i], len(v))
		}
	}
	for _, line := range table {
		for i, v := range line {
			fmt.Fprintf(w, "%*s  ", width[i], v)
		}
		fmt.Fprintln(w)
	}
}
