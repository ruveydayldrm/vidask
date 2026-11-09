import "@testing-library/jest-dom/vitest";

// jsdom lacks these; components use them for auto-scroll and media queries.
Element.prototype.scrollIntoView = function () {};
if (!window.matchMedia) {
  window.matchMedia = (query: string) =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    }) as unknown as MediaQueryList;
}
