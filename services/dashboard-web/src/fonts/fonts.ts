import localFont from "next/font/local";

// Vendored IBM Plex (OFL, see ./OFL.txt) so builds need no network. next/font/local cannot
// split a family by unicode-range, so each family is a latin and a latin-ext face; the CSS
// variables are chained in packages/ui styles (--font-plex-<family>-latin / -ext).

export const sansLatin = localFont({
    src: [
        { path: "./ibm-plex-sans-latin-400-normal.woff2", weight: "400", style: "normal" },
        { path: "./ibm-plex-sans-latin-500-normal.woff2", weight: "500", style: "normal" },
        { path: "./ibm-plex-sans-latin-600-normal.woff2", weight: "600", style: "normal" },
    ],
    declarations: [
        {
            prop: "unicode-range",
            value: "U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD",
        },
    ],
    variable: "--font-plex-sans-latin",
    adjustFontFallback: false,
    fallback: [],
});

export const sansExt = localFont({
    src: [
        { path: "./ibm-plex-sans-latin-ext-400-normal.woff2", weight: "400", style: "normal" },
        { path: "./ibm-plex-sans-latin-ext-500-normal.woff2", weight: "500", style: "normal" },
        { path: "./ibm-plex-sans-latin-ext-600-normal.woff2", weight: "600", style: "normal" },
    ],
    declarations: [
        {
            prop: "unicode-range",
            value: "U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF",
        },
    ],
    variable: "--font-plex-sans-ext",
    adjustFontFallback: false,
    fallback: [],
});

export const monoLatin = localFont({
    src: [
        { path: "./ibm-plex-mono-latin-400-normal.woff2", weight: "400", style: "normal" },
        { path: "./ibm-plex-mono-latin-500-normal.woff2", weight: "500", style: "normal" },
    ],
    declarations: [
        {
            prop: "unicode-range",
            value: "U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD",
        },
    ],
    variable: "--font-plex-mono-latin",
    adjustFontFallback: false,
    fallback: [],
});

export const monoExt = localFont({
    src: [
        { path: "./ibm-plex-mono-latin-ext-400-normal.woff2", weight: "400", style: "normal" },
        { path: "./ibm-plex-mono-latin-ext-500-normal.woff2", weight: "500", style: "normal" },
    ],
    declarations: [
        {
            prop: "unicode-range",
            value: "U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF",
        },
    ],
    variable: "--font-plex-mono-ext",
    adjustFontFallback: false,
    fallback: [],
});

export const serifLatin = localFont({
    src: [
        { path: "./ibm-plex-serif-latin-500-normal.woff2", weight: "500", style: "normal" },
        { path: "./ibm-plex-serif-latin-600-normal.woff2", weight: "600", style: "normal" },
    ],
    declarations: [
        {
            prop: "unicode-range",
            value: "U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD",
        },
    ],
    variable: "--font-plex-serif-latin",
    adjustFontFallback: false,
    fallback: [],
});

export const serifExt = localFont({
    src: [
        { path: "./ibm-plex-serif-latin-ext-500-normal.woff2", weight: "500", style: "normal" },
        { path: "./ibm-plex-serif-latin-ext-600-normal.woff2", weight: "600", style: "normal" },
    ],
    declarations: [
        {
            prop: "unicode-range",
            value: "U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF",
        },
    ],
    variable: "--font-plex-serif-ext",
    adjustFontFallback: false,
    fallback: [],
});
