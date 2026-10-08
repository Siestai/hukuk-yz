/** "18" and "18/A" are numbered articles ("m. 18"); "Ek 3" and "Geçici 8" are named as they are. */
export function isNumberedArticle(articleNo: string): boolean {
    return /^\d/.test(articleNo);
}
