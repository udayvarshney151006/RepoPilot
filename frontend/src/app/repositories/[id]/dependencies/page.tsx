import { DependencyGraph } from "@/components/dependency-graph";
export default async function DependenciesPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  return <DependencyGraph id={(await params).id} />;
}
