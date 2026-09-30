import { Evaluations } from "@/components/evaluations";
export default async function EvaluationsPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  return <Evaluations id={(await params).id} />;
}
