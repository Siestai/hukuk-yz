import localFont from "next/font/local";

// Vendored Newsreader and Figtree (OFL, see ./OFL-glarus.txt) for the chat app's "Liman" look.
// A separate module from ./fonts.ts, so the dashboard does not ship these. Same latin and
// latin-ext split as the Plex faces; the CSS variables are chained in services/web globals.css.

export const newsreaderLatin = localFont({
    src: [
        { path: "./newsreader-latin-400-normal.woff2", weight: "400", style: "normal" },
        { path: "./newsreader-latin-500-normal.woff2", weight: "500", style: "normal" },
        { path: "./newsreader-latin-600-normal.woff2", weight: "600", style: "normal" },
        { path: "./newsreader-latin-400-italic.woff2", weight: "400", style: "italic" },
    ],
    declarations: [
        {
            prop: "unicode-range",
            value: "U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD",
        },
    ],
    variable: "--font-newsreader-latin",
    adjustFontFallback: false,
    fallback: [],
});

export const newsreaderExt = localFont({
    src: [
        { path: "./newsreader-latin-ext-400-normal.woff2", weight: "400", style: "normal" },
        { path: "./newsreader-latin-ext-500-normal.woff2", weight: "500", style: "normal" },
        { path: "./newsreader-latin-ext-600-normal.woff2", weight: "600", style: "normal" },
        { path: "./newsreader-latin-ext-400-italic.woff2", weight: "400", style: "italic" },
    ],
    declarations: [
        {
            prop: "unicode-range",
            value: "U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF",
        },
    ],
    variable: "--font-newsreader-ext",
    adjustFontFallback: false,
    fallback: [],
});

export const figtreeLatin = localFont({
    src: [
        { path: "./figtree-latin-400-normal.woff2", weight: "400", style: "normal" },
        { path: "./figtree-latin-500-normal.woff2", weight: "500", style: "normal" },
        { path: "./figtree-latin-600-normal.woff2", weight: "600", style: "normal" },
        { path: "./figtree-latin-700-normal.woff2", weight: "700", style: "normal" },
    ],
    declarations: [
        {
            prop: "unicode-range",
            value: "U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD",
        },
    ],
    variable: "--font-figtree-latin",
    adjustFontFallback: false,
    fallback: [],
});

export const figtreeExt = localFont({
    src: [
        { path: "./figtree-latin-ext-400-normal.woff2", weight: "400", style: "normal" },
        { path: "./figtree-latin-ext-500-normal.woff2", weight: "500", style: "normal" },
        { path: "./figtree-latin-ext-600-normal.woff2", weight: "600", style: "normal" },
        { path: "./figtree-latin-ext-700-normal.woff2", weight: "700", style: "normal" },
    ],
    declarations: [
        {
            prop: "unicode-range",
            value: "U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF",
        },
    ],
    variable: "--font-figtree-ext",
    adjustFontFallback: false,
    fallback: [],
});

/** The class names that define the font CSS variables; they go on the chat app's `<html>`. */
export const glarusFontVariables = [newsreaderLatin, newsreaderExt, figtreeLatin, figtreeExt]
    .map((font) => font.variable)
    .join(" ");
