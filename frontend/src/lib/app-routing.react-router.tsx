"use client";

import * as React from "react";
import {
  Link as RouterLink,
  useLocation,
  useNavigate,
  useSearchParams,
} from "react-router-dom";

import type {
  AppLinkProps,
  AppNavigationOptions,
  AppRouter,
} from "./app-routing";

export const AppLink = React.forwardRef<HTMLAnchorElement, AppLinkProps>(
  function AppLink({ href, replace, state, ...props }, ref) {
    return (
      <RouterLink
        ref={ref}
        replace={replace}
        state={state}
        to={href}
        {...props}
      />
    );
  }
);

export function useAppPathname() {
  return useLocation().pathname;
}

export function useAppRouter(): AppRouter {
  const navigate = useNavigate();
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
        navigate(-1);
      },
      forward() {
        if (!isMountedRef.current) {
          return;
        }
        navigate(1);
      },
      push(href: string, options?: AppNavigationOptions) {
        if (!isMountedRef.current) {
          return;
        }
        navigate(href, {
          flushSync: options?.flushSync,
          preventScrollReset: options?.scroll === false,
        });
      },
      refresh() {
        if (!isMountedRef.current) {
          return;
        }
        window.location.reload();
      },
      replace(href: string, options?: AppNavigationOptions) {
        if (!isMountedRef.current) {
          return;
        }
        navigate(href, {
          flushSync: options?.flushSync,
          preventScrollReset: options?.scroll === false,
          replace: true,
        });
      },
    }),
    [navigate]
  );
}

export function useAppSearchParams() {
  const [searchParams] = useSearchParams();
  return searchParams;
}
