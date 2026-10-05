declare module "react/jsx-runtime" {
  export const jsx: any;
  export const jsxs: any;
  export const Fragment: any;
  export namespace JSX {
    interface Element extends React.ReactElement {}
    interface ElementChildrenAttribute { children: {} }
    interface IntrinsicAttributes { key?: React.Key }
    interface IntrinsicElements { [tag: string]: any }
    type ElementType = string | ((props: any) => React.ReactNode);
  }
}
