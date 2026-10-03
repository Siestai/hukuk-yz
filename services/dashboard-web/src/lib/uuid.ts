export const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;

export const isUuid = (value: string) => new RegExp(`^${UUID.source}$`, "i").test(value);
