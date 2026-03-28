"use client";

import * as React from "react";
import NextLink from "next/link";
import {
  usePathname,
  useRouter,
  useSearchParams,
} from "next/navigation";

export interface AppLinkProps
  extends Omit<React.ComponentPropsWithoutRef<"a">, "href"> {
  href: string;
  replace?: boolean;
  state?: unknown;
}

export interface AppNavigationOptions {
  flushSync?: boolean;
  scroll?: boolean;
}

export interface AppRouter {
  back(): void;
  forward(): void;
  push(href: string, options?: AppNavigationOptions): void;
  refresh(): void;
  replace(href: string, options?: AppNavigationOptions): void;
}

function normalizeNavigationOptions(
  options?: AppNavigationOptions
) {
  if (!options) {
    return undefined;
  }

  return {
    scroll: options.scroll,
  };
}

export const AppLink = React.forwardRef<HTMLAnchorElement, AppLinkProps>(
  function AppLink({ href, replace, ...props }, ref) {
    return <NextLink ref={ref} href={href} replace={replace} {...props} />;
  },
);

export function useAppPathname() {
  return usePathname();
}

export function useAppRouter(): AppRouter {
  const router = useRouter();
  const isMountedRef = React.useRef(true);

  React.useEffect(() => {
    isMountedRef.current = true;

    return () => {
      isMountedRef.current = false;
    };
  }, []);

  return React.useMemo(
    () => ({
      back() {
        if (!isMountedRef.current) {
          return;
        }
        router.back();
      },
      forward() {
        if (!isMountedRef.current) {
          return;
        }
        router.forward();
      },
      push(href, options) {
        if (!isMountedRef.current) {
          return;
        }
        router.push(href, normalizeNavigationOptions(options));
      },
      refresh() {
        if (!isMountedRef.current) {
          return;
        }
        router.refresh();
      },
      replace(href, options) {
        if (!isMountedRef.current) {
          return;
        }
        router.replace(href, normalizeNavigationOptions(options));
      },
    }),
    [router]
  );
}

export function useAppSearchParams() {
  return useSearchParams();
}
