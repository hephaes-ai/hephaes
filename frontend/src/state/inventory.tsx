import {
  createContext,
  type PropsWithChildren,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
} from "react";

import { ApiError, listAssets, registerAsset, type AssetListItem, type AssetRegistrationResponse } from "../lib/api";

type InventorySnapshot =
  | { status: "idle"; assets: AssetListItem[]; error: null }
  | { status: "loading"; assets: AssetListItem[]; error: null }
  | { status: "ready"; assets: AssetListItem[]; error: null }
  | { status: "error"; assets: AssetListItem[]; error: string };

type LoadInventoryOptions = {
  force?: boolean;
  signal?: AbortSignal;
};

type InventoryContextValue = {
  inventory: InventorySnapshot;
  loadInventory: (options?: LoadInventoryOptions) => Promise<void>;
  registerAssetPath: (filePath: string) => Promise<AssetRegistrationResponse>;
};

const InventoryContext = createContext<InventoryContextValue | null>(null);

function toErrorMessage(error: unknown, fallback: string) {
  if (error instanceof ApiError || error instanceof Error) {
    return error.message;
  }
  return fallback;
}

export function InventoryProvider({ children }: PropsWithChildren) {
  const [inventory, setInventory] = useState<InventorySnapshot>({
    status: "idle",
    assets: [],
    error: null,
  });
  const hasLoadedRef = useRef(false);
  const isLoadingRef = useRef(false);

  const loadInventory = useCallback(
    async (options: LoadInventoryOptions = {}) => {
      if (!options.force && (hasLoadedRef.current || isLoadingRef.current)) {
        return;
      }

      isLoadingRef.current = true;
      setInventory((current) => ({
        status: "loading",
        assets: current.assets,
        error: null,
      }));

      try {
        const assets = await listAssets(options.signal);
        hasLoadedRef.current = true;
        setInventory({
          status: "ready",
          assets,
          error: null,
        });
      } catch (error) {
        if (options.signal?.aborted) {
          return;
        }

        setInventory((current) => ({
          status: "error",
          assets: current.assets,
          error: toErrorMessage(error, "Unable to load inventory"),
        }));
      } finally {
        isLoadingRef.current = false;
      }
    },
    [],
  );

  const registerAssetPath = useCallback(async (filePath: string) => {
    const asset = await registerAsset({ file_path: filePath });
    hasLoadedRef.current = true;
    setInventory((current) => ({
      status: "ready",
      assets: [asset, ...current.assets.filter((currentAsset) => currentAsset.id !== asset.id)],
      error: null,
    }));
    return asset;
  }, []);

  const value = useMemo(
    () => ({
      inventory,
      loadInventory,
      registerAssetPath,
    }),
    [inventory, loadInventory, registerAssetPath],
  );

  return <InventoryContext.Provider value={value}>{children}</InventoryContext.Provider>;
}

export function useInventory() {
  const value = useContext(InventoryContext);
  if (value === null) {
    throw new Error("useInventory must be used inside InventoryProvider");
  }
  return value;
}
