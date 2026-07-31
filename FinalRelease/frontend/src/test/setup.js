const values = new Map();

const localStorage = {
  clear() {
    values.clear();
  },
  getItem(key) {
    return values.has(String(key)) ? values.get(String(key)) : null;
  },
  key(index) {
    return [...values.keys()][index] ?? null;
  },
  get length() {
    return values.size;
  },
  removeItem(key) {
    values.delete(String(key));
  },
  setItem(key, value) {
    values.set(String(key), String(value));
  },
};

Object.defineProperty(window, 'localStorage', {
  configurable: true,
  value: localStorage,
});
