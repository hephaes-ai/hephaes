import { AssetDetailPage } from "@/components/asset-detail-page";

interface AssetPageProps {
  params: Promise<{
    assetId: string;
  }>;
}

export default async function Page({ params }: AssetPageProps) {
  const { assetId } = await params;

  return <AssetDetailPage assetId={assetId} />;
}
