import "server-only";

export type Quote = { text: string; author: string };

/** A random quote for the login panel. Content, not UI text: lives in content/login-quotes.<locale>.json. */
export async function pickQuote(
    locale: string,
    random: () => number = Math.random,
): Promise<Quote> {
    const quotes: Quote[] = (await import(`../../content/login-quotes.${locale}.json`)).default;
    const quote = quotes[Math.floor(random() * quotes.length)];
    if (!quote) throw new Error(`No login quotes for locale ${locale}`);
    return quote;
}
