// Declarações MÍNIMAS de React 19 para checagem de tipos offline (sem @types/react).
// Em ambiente com npm, use tsconfig.json + @types/react (devDependency) — este arquivo não é usado lá.
declare namespace React {
  type ReactNode = ReactElement | string | number | bigint | boolean | null | undefined | Iterable<ReactNode>;
  interface ReactElement { type: any; props: any; key: string | null }
  type Key = string | number;
  type SetStateAction<S> = S | ((prev: S) => S);
  type Dispatch<A> = (value: A) => void;
  type FC<P = {}> = (props: P) => ReactNode;
  interface RefObject<T> { current: T }
  interface Context<T> { Provider: FC<{ value: T; children?: ReactNode }> }
  interface SyntheticEvent<T = Element> { target: any; currentTarget: T; preventDefault(): void; stopPropagation(): void }
  interface FormEvent<T = Element> extends SyntheticEvent<T> {}
  interface ChangeEvent<T = Element> extends SyntheticEvent<T> { target: any }
  interface KeyboardEvent<T = Element> extends SyntheticEvent<T> { key: string }
  interface MouseEvent<T = Element> extends SyntheticEvent<T> { button: number; metaKey: boolean; ctrlKey: boolean; shiftKey: boolean }
  type CSSProperties = { [k: string]: string | number | undefined };
}
declare module "react" {
  export = React;
  export as namespace React;
}
declare namespace React {
  function useState<S>(initial: S | (() => S)): [S, Dispatch<SetStateAction<S>>];
  function useEffect(effect: () => void | (() => void), deps?: readonly unknown[]): void;
  function useMemo<T>(factory: () => T, deps: readonly unknown[]): T;
  function useCallback<T extends (...args: any[]) => any>(cb: T, deps: readonly unknown[]): T;
  function useRef<T>(initial: T): RefObject<T>;
  function useContext<T>(ctx: Context<T>): T;
  function createContext<T>(defaultValue: T): Context<T>;
  function useId(): string;
  class Component<P = {}, S = {}> { constructor(props: P); props: P; state: S; setState(s: Partial<S>): void; render(): ReactNode; }
  const Fragment: FC<{ children?: ReactNode; key?: Key }>;
  const StrictMode: FC<{ children?: ReactNode }>;
}
declare namespace JSX {
  interface Element extends React.ReactElement {}
  interface ElementChildrenAttribute { children: {} }
  interface IntrinsicAttributes { key?: React.Key }
  interface IntrinsicElements { [tag: string]: any }
  type ElementType = string | ((props: any) => React.ReactNode);
}
