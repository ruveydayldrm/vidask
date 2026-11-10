import type { VideoMeta } from "./types";

const yt = (id: string) => ({
  video_id: id,
  url: `https://www.youtube.com/watch?v=${id}`,
  thumbnail: `https://i.ytimg.com/vi/${id}/hqdefault.jpg`,
});

/** Public, captioned example videos (the same ones the eval set uses). */
export const EXAMPLES: VideoMeta[] = [
  { ...yt("OVvTv9Hy91Q"), title: "What Are APIs? - Simply Explained", channel: "Simply Explained", duration: 409, language: "en" },
  { ...yt("hcsn-XT_xd4"), title: "Yapay Zeka · Türkçe Kısa Belgesel", channel: "Bilim 101", duration: 344, language: "tr" },
  { ...yt("knV86FlSXJ8"), title: "Hash tables in 4 minutes", channel: "Michael Sambol", duration: 232, language: "en" },
  { ...yt("r3P58Y1OL0g"), title: "Blokzincir (Blockchain) Nedir? Nasıl Çalışır?", channel: "TÜBİTAK Bilim Genç", duration: 389, language: "tr" },
];
