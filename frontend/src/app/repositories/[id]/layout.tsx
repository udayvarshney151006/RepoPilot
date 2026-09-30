import { Workspace } from "@/components/workspace";
export default async function WorkspaceLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <Workspace id={id}>{children}</Workspace>;
}
