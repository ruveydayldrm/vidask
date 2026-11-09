import { VideoView } from "@/components/workspace/video-view";

export default async function VideoPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ job?: string }>;
}) {
  const { id } = await params;
  const { job } = await searchParams;
  return <VideoView id={id} jobParam={job} />;
}
