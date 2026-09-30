import { FileExplorer } from "@/components/file-explorer";
export default async function FilesPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  return <FileExplorer id={(await params).id} />;
}
