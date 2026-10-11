import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { uploadFile } from "./upload-file";

class FakeRequest {
    static last: FakeRequest;
    method = "";
    url = "";
    responseType = "";
    headers: Record<string, string> = {};
    status = 0;
    response: unknown = null;
    body: FormData | null = null;
    upload: { onprogress: ((event: ProgressEvent) => void) | null } = { onprogress: null };
    onload: (() => void) | null = null;
    onerror: (() => void) | null = null;
    ontimeout: (() => void) | null = null;
    constructor() {
        FakeRequest.last = this;
    }
    open(method: string, url: string) {
        this.method = method;
        this.url = url;
    }
    setRequestHeader(name: string, value: string) {
        this.headers[name] = value;
    }
    send(body: FormData) {
        this.body = body;
    }
    answer(status: number, response: unknown) {
        this.status = status;
        this.response = response;
        this.onload?.();
    }
}

beforeEach(() => vi.stubGlobal("XMLHttpRequest", FakeRequest));
afterEach(() => vi.unstubAllGlobals());

const pdf = new File(["%PDF"], "k.pdf", { type: "application/pdf" });

describe("uploadFile", () => {
    it("posts the file and the filled fields as multipart and reports progress", async () => {
        const progress = vi.fn();
        const done = uploadFile(
            "/api/files",
            pdf,
            { doc_type: "karar", note: "", doc_date: "2020-01-02" },
            progress,
        );
        const request = FakeRequest.last;
        expect([request.method, request.url, request.responseType]).toEqual([
            "POST",
            "/api/files",
            "json",
        ]);
        expect(request.headers).toEqual({ "X-Requested-With": "XMLHttpRequest" });
        expect(request.body?.get("doc_type")).toBe("karar");
        expect(request.body?.get("doc_date")).toBe("2020-01-02");
        expect(request.body?.has("note")).toBe(false);
        expect((request.body?.get("file") as File).name).toBe("k.pdf");
        request.upload.onprogress?.({
            lengthComputable: true,
            loaded: 1,
            total: 4,
        } as ProgressEvent);
        expect(progress).toHaveBeenCalledWith(0.25);
        request.answer(201, { id: "f1" });
        expect(await done).toEqual({ ok: true, file: { id: "f1" } });
    });

    it("returns the error code and params of the API", async () => {
        const done = uploadFile("/api/files", pdf, {}, vi.fn());
        FakeRequest.last.answer(409, {
            error: { code: "duplicate_file", params: { file_id: "f1", archived: true } },
        });
        expect(await done).toEqual({
            ok: false,
            code: "duplicate_file",
            params: { file_id: "f1", archived: true },
        });
    });

    it("calls any 413 a file that is too large, also the proxy's own", async () => {
        const done = uploadFile("/api/files", pdf, {}, vi.fn());
        FakeRequest.last.answer(413, { error: { code: "payload_too_large", params: {} } });
        expect(await done).toMatchObject({ ok: false, code: "file_too_large" });
    });

    it("turns a lost connection and a timeout into upstream_unavailable", async () => {
        const first = uploadFile("/api/files", pdf, {}, vi.fn());
        FakeRequest.last.onerror?.();
        expect(await first).toMatchObject({ ok: false, code: "upstream_unavailable" });
        const second = uploadFile("/api/files", pdf, {}, vi.fn());
        FakeRequest.last.ontimeout?.();
        expect(await second).toMatchObject({ ok: false, code: "upstream_unavailable" });
    });

    it("has no code for an answer that is not the API's", async () => {
        const done = uploadFile("/api/files", pdf, {}, vi.fn());
        FakeRequest.last.answer(502, null);
        expect(await done).toEqual({ ok: false, code: undefined, params: {} });
    });
});
