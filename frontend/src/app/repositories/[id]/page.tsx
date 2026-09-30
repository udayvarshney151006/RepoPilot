import { Overview } from "@/components/overview";
export default async function RepositoryPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <Overview id={id} />;
}
