"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

export type Lang = "tr" | "en";

const en = {
  "app.tagline": "Ask any YouTube video. Get answers with the exact second.",
  "home.title": "Ask anything about any video.",
  "home.subtitle":
    "Paste a YouTube link. VidAsk reads the transcript and what's on screen, then answers with timestamps you can click — and tells you when the video doesn't say.",
  "home.placeholder": "Paste a YouTube link…",
  "home.analyze": "Analyze",
  "home.analyzing": "Starting…",
  "home.invalid": "That doesn't look like a YouTube link.",
  "home.examples": "Try an example",
  "home.recent": "Recently analyzed",
  "home.recentEmpty": "Videos you analyze will appear here.",
  "home.local": "Runs 100% locally · open-source models",
  "home.open": "Open",
  "home.pasteHint": "Tip: press / to focus · Enter to analyze",
  "stage.metadata": "Video details",
  "stage.transcript": "Transcript",
  "stage.vision": "On-screen analysis",
  "stage.indexing": "Indexing",
  "stage.insights": "Summary & chapters",
  "stage.skipped": "Skipped",
  "processing.title": "Getting the video ready",
  "processing.subtitle": "This happens once per video — next time it's instant.",
  "processing.elapsed": "Elapsed",
  "processing.failed": "Processing failed",
  "processing.retry": "Try again",
  "processing.home": "Back home",
  "tips.0": "Click any [mm:ss] in an answer to jump the player to that exact moment.",
  "tips.1": "Ask follow-ups — VidAsk remembers the conversation.",
  "tips.2": "If the video doesn't cover something, VidAsk says so instead of guessing.",
  "tips.3": "Press / to jump to the question box, Space to play or pause.",
  "tips.4": "Every citation is checked against what was actually retrieved.",
  "tabs.summary": "Summary",
  "tabs.chapters": "Chapters",
  "tabs.transcript": "Transcript",
  "tabs.chat": "Chat",
  "player.blockedTitle": "This video can only be played on YouTube",
  "player.blockedBody":
    "The owner turned off playback on other sites. Q&A still works — timestamps open YouTube at that second.",
  "player.openYoutube": "Watch on YouTube",
  "summary.empty": "No summary was generated for this video.",
  "summary.pending":
    "Writing the summary and chapters in the background — you can already ask questions.",
  "summary.source": "Transcript source",
  "summary.language": "Language",
  "summary.vision": "On-screen analysis",
  "summary.on": "On",
  "summary.off": "Off",
  "source.manual_captions": "Manual captions",
  "source.auto_captions": "Auto captions",
  "source.whisper": "Whisper (speech-to-text)",
  "chapters.empty": "No chapters were generated.",
  "transcript.search": "Search transcript…",
  "transcript.matches": "{n} matches",
  "transcript.noMatches": "No matches",
  "transcript.follow": "Follow playback",
  "transcript.onScreen": "On screen",
  "chat.title": "Ask the video",
  "chat.placeholder": "Ask a question about this video…",
  "chat.send": "Send",
  "chat.stop": "Stop",
  "chat.suggested": "Suggested questions",
  "chat.emptyTitle": "What do you want to know?",
  "chat.emptyBody": "Answers cite the moment they come from. Click a timestamp to jump there.",
  "chat.thinking": "Reading the video…",
  "chat.sources": "Sources",
  "chat.strategy.full": "Full transcript",
  "chat.strategy.rag": "Hybrid search",
  "chat.notCovered": "Not covered in the video",
  "chat.error": "Something went wrong",
  "chat.clear": "New chat",
  "chat.onScreen": "shown on screen",
  "settings.title": "Settings",
  "settings.provider": "LLM provider",
  "settings.model": "Model",
  "settings.vision": "On-screen analysis (OCR)",
  "settings.visionHint":
    "Reads slides and code from scene changes. Slower on CPU; applies to new videos.",
  "settings.reranker": "Reranker",
  "settings.rerankerHint":
    "Cross-encoder reranking for long videos. Better answers, slightly slower.",
  "settings.noKey": "No API key configured",
  "settings.save": "Save",
  "settings.saved": "Saved",
  "settings.models": "Models in use",
  "shortcuts.title": "Keyboard shortcuts",
  "shortcuts.focus": "Focus the question box",
  "shortcuts.play": "Play / pause",
  "shortcuts.back": "Back 10 seconds",
  "shortcuts.fwd": "Forward 10 seconds",
  "shortcuts.help": "Show shortcuts",
  "theme.toggle": "Toggle theme",
  "lang.toggle": "Türkçe'ye geç",
  "error.network": "Can't reach the VidAsk backend. Is it running on port 8000?",
  "error.notFound": "This video hasn't been analyzed yet.",
  "error.generic": "Something went wrong.",
};

const tr: Record<keyof typeof en, string> = {
  "app.tagline": "Herhangi bir YouTube videosuna sorun. Cevabı tam saniyesiyle alın.",
  "home.title": "Herhangi bir videoya her şeyi sorun.",
  "home.subtitle":
    "Bir YouTube linki yapıştırın. VidAsk konuşmayı ve ekranda gösterilenleri okur; cevapları tıklanabilir zaman damgalarıyla verir — videoda geçmeyen bir şeyi de uydurmaz.",
  "home.placeholder": "YouTube linkini yapıştırın…",
  "home.analyze": "Analiz et",
  "home.analyzing": "Başlatılıyor…",
  "home.invalid": "Bu bir YouTube linkine benzemiyor.",
  "home.examples": "Bir örnekle deneyin",
  "home.recent": "Son analiz edilenler",
  "home.recentEmpty": "Analiz ettiğiniz videolar burada görünecek.",
  "home.local": "%100 lokal çalışır · açık kaynak modeller",
  "home.open": "Aç",
  "home.pasteHint": "İpucu: odaklanmak için / · analiz için Enter",
  "stage.metadata": "Video bilgileri",
  "stage.transcript": "Transkript",
  "stage.vision": "Ekran analizi",
  "stage.indexing": "İndeksleme",
  "stage.insights": "Özet ve bölümler",
  "stage.skipped": "Atlandı",
  "processing.title": "Video hazırlanıyor",
  "processing.subtitle": "Bu işlem her video için bir kez yapılır — sonraki seferde anında açılır.",
  "processing.elapsed": "Geçen süre",
  "processing.failed": "İşlem başarısız oldu",
  "processing.retry": "Tekrar dene",
  "processing.home": "Ana sayfa",
  "tips.0": "Cevaptaki herhangi bir [dd:ss] etiketine tıklayın, oynatıcı tam o ana atlasın.",
  "tips.1": "Takip soruları sorabilirsiniz — VidAsk sohbeti hatırlar.",
  "tips.2": "Videoda geçmeyen bir şeyi sorarsanız VidAsk tahmin etmez, açıkça söyler.",
  "tips.3": "Soru kutusu için / tuşuna, oynat/duraklat için Boşluk tuşuna basın.",
  "tips.4": "Her zaman damgası, gerçekten getirilen parçalara karşı doğrulanır.",
  "tabs.summary": "Özet",
  "tabs.chapters": "Bölümler",
  "tabs.transcript": "Transkript",
  "tabs.chat": "Sohbet",
  "player.blockedTitle": "Bu video yalnızca YouTube'da oynatılabiliyor",
  "player.blockedBody":
    "Video sahibi başka sitelerde oynatmayı kapatmış. Soru-cevap yine çalışır; zaman damgaları videoyu YouTube'da o saniyeden açar.",
  "player.openYoutube": "YouTube'da izle",
  "summary.empty": "Bu video için özet oluşturulamadı.",
  "summary.pending": "Özet ve bölümler arka planda hazırlanıyor — şimdiden soru sorabilirsiniz.",
  "summary.source": "Transkript kaynağı",
  "summary.language": "Dil",
  "summary.vision": "Ekran analizi",
  "summary.on": "Açık",
  "summary.off": "Kapalı",
  "source.manual_captions": "Manuel altyazı",
  "source.auto_captions": "Otomatik altyazı",
  "source.whisper": "Whisper (konuşmadan metne)",
  "chapters.empty": "Bölüm oluşturulamadı.",
  "transcript.search": "Transkriptte ara…",
  "transcript.matches": "{n} eşleşme",
  "transcript.noMatches": "Eşleşme yok",
  "transcript.follow": "Oynatmayı takip et",
  "transcript.onScreen": "Ekranda",
  "chat.title": "Videoya sorun",
  "chat.placeholder": "Bu video hakkında bir soru sorun…",
  "chat.send": "Gönder",
  "chat.stop": "Durdur",
  "chat.suggested": "Önerilen sorular",
  "chat.emptyTitle": "Ne öğrenmek istersiniz?",
  "chat.emptyBody":
    "Cevaplar bilginin geçtiği anı gösterir. O ana gitmek için zaman damgasına tıklayın.",
  "chat.thinking": "Video okunuyor…",
  "chat.sources": "Kaynaklar",
  "chat.strategy.full": "Tüm transkript",
  "chat.strategy.rag": "Hibrit arama",
  "chat.notCovered": "Videoda geçmiyor",
  "chat.error": "Bir şeyler ters gitti",
  "chat.clear": "Yeni sohbet",
  "chat.onScreen": "ekranda gösterilen",
  "settings.title": "Ayarlar",
  "settings.provider": "LLM sağlayıcı",
  "settings.model": "Model",
  "settings.vision": "Ekran analizi (OCR)",
  "settings.visionHint":
    "Sahne değişimlerinde slayt ve kodları okur. CPU'da yavaştır; yeni videolara uygulanır.",
  "settings.reranker": "Yeniden sıralayıcı",
  "settings.rerankerHint":
    "Uzun videolarda cross-encoder ile yeniden sıralama. Daha iyi cevap, biraz daha yavaş.",
  "settings.noKey": "API anahtarı tanımlı değil",
  "settings.save": "Kaydet",
  "settings.saved": "Kaydedildi",
  "settings.models": "Kullanılan modeller",
  "shortcuts.title": "Klavye kısayolları",
  "shortcuts.focus": "Soru kutusuna odaklan",
  "shortcuts.play": "Oynat / duraklat",
  "shortcuts.back": "10 saniye geri",
  "shortcuts.fwd": "10 saniye ileri",
  "shortcuts.help": "Kısayolları göster",
  "theme.toggle": "Temayı değiştir",
  "lang.toggle": "Switch to English",
  "error.network": "VidAsk sunucusuna ulaşılamıyor. 8000 portunda çalışıyor mu?",
  "error.notFound": "Bu video henüz analiz edilmedi.",
  "error.generic": "Bir şeyler ters gitti.",
};

export type TKey = keyof typeof en;
const dictionaries: Record<Lang, Record<TKey, string>> = { en, tr };

interface I18nValue {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: (key: TKey, vars?: Record<string, string | number>) => string;
}

const I18nContext = createContext<I18nValue | null>(null);

export function translate(lang: Lang, key: TKey, vars?: Record<string, string | number>): string {
  let s = dictionaries[lang][key] ?? en[key] ?? key;
  if (vars) for (const [k, v] of Object.entries(vars)) s = s.replace(`{${k}}`, String(v));
  return s;
}

export function I18nProvider({ children, initial }: { children: React.ReactNode; initial?: Lang }) {
  const [lang, setLangState] = useState<Lang>(initial ?? "en");

  useEffect(() => {
    if (initial) return;
    let stored: string | null = null;
    try {
      stored = localStorage.getItem("vidask.lang");
    } catch {
      /* storage unavailable */
    }
    const detected = stored ?? (navigator.language?.toLowerCase().startsWith("tr") ? "tr" : "en");
    if (detected === "tr" || detected === "en") setLangState(detected);
  }, [initial]);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    try {
      localStorage.setItem("vidask.lang", l);
    } catch {
      /* ignore */
    }
  }, []);

  const value = useMemo<I18nValue>(
    () => ({ lang, setLang, t: (key, vars) => translate(lang, key, vars) }),
    [lang, setLang],
  );
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nValue {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used inside <I18nProvider>");
  return ctx;
}
