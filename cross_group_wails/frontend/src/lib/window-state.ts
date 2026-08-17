import { WindowIsMaximised, WindowToggleMaximise } from "../../wailsjs/runtime/runtime";

type Listener = (maximized: boolean) => void;

const listeners = new Set<Listener>();
let cached = false;
let listening = false;

function emit(value: boolean) {
  cached = value;
  listeners.forEach((fn) => fn(value));
}

async function probe(): Promise<boolean> {
  try {
    return await WindowIsMaximised();
  } catch {
    return cached;
  }
}

export function getMaximized(): boolean {
  return cached;
}

export function subscribeMaximized(listener: Listener): () => void {
  listeners.add(listener);
  listener(cached);
  if (!listening) {
    listening = true;
    void refreshMaximized();
    window.addEventListener("focus", () => {
      void refreshMaximized();
    });
    window.addEventListener("resize", () => {
      void refreshMaximized();
    });
  }
  return () => {
    listeners.delete(listener);
  };
}

export async function refreshMaximized(): Promise<boolean> {
  const value = await probe();
  if (value !== cached) emit(value);
  else emit(value);
  return value;
}

export async function toggleMaximized(): Promise<boolean> {
  await WindowToggleMaximise();
  return refreshMaximized();
}
