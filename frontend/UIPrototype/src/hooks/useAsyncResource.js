import { useCallback, useEffect, useRef, useState } from 'react';

export default function useAsyncResource(loader, dependencies = []) {
  const loaderRef = useRef(loader);
  loaderRef.current = loader;

  const [state, setState] = useState({
    data: null,
    error: null,
    loading: true,
  });

  const load = useCallback(async () => {
    setState((current) => ({ ...current, error: null, loading: true }));

    try {
      const data = await loaderRef.current();
      setState({ data, error: null, loading: false });
      return data;
    } catch (error) {
      setState((current) => ({ ...current, error, loading: false }));
      return null;
    }
  }, dependencies);

  useEffect(() => {
    let active = true;

    const run = async () => {
      setState((current) => ({ ...current, error: null, loading: true }));
      try {
        const data = await loaderRef.current();
        if (active) setState({ data, error: null, loading: false });
      } catch (error) {
        if (active) setState((current) => ({ ...current, error, loading: false }));
      }
    };

    run();
    return () => {
      active = false;
    };
  }, [load]);

  return { ...state, reload: load };
}
