"use client";

import * as React from "react";
import NextLink from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

type AppLinkProps = React.ComponentProps<typeof NextLink>;

export const AppLink = React.forwardRef<HTMLAnchorElement, AppLinkProps>(
  function AppLink(props, ref) {
    return <NextLink ref={ref} {...props} />;
  },
);

export function useAppPathname() {
  return usePathname();
}

export function useAppRouter() {
  return useRouter();
}

export function useAppSearchParams() {
  return useSearchParams();
}
