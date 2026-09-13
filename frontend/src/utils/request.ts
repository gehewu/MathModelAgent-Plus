import axios from "axios";

/** 创建 axios 实例 */
const service = axios.create({
	baseURL: import.meta.env.VITE_API_BASE_URL,
	timeout: 10000,
});

/** 请求拦截器 */
service.interceptors.request.use(
	(config) => {
		return config;
	},
	(error) => {
		console.log(error);
		return Promise.reject(error);
	},
);

/**
 * 从 axios 错误中提取可读的错误信息：
 * 优先取后端 FastAPI 返回的 detail（字符串或 422 校验错误数组），
 * 其次取 axios 自带 message（网络错误/超时等），最后兜底通用文案。
 */
export function getErrorMessage(error: unknown): string {
	const err = error as {
		displayMessage?: string;
		response?: { data?: { detail?: unknown } };
		message?: string;
	};
	if (err?.displayMessage) {
		return err.displayMessage;
	}
	const detail = err?.response?.data?.detail;
	if (typeof detail === "string") {
		return detail;
	}
	if (Array.isArray(detail)) {
		const messages = detail
			.map((item) => {
				const msg = (item as { msg?: string })?.msg;
				return msg || "";
			})
			.filter(Boolean);
		if (messages.length > 0) {
			return messages.join("; ");
		}
	}
	return err?.message || "请求失败";
}

/** 响应拦截器：统一提取后端错误详情挂到 error.displayMessage */
service.interceptors.response.use(
	(response) => {
		return response;
	},
	(error) => {
		const detail = error?.response?.data?.detail;
		let display = "";
		if (typeof detail === "string") {
			display = detail;
		} else if (Array.isArray(detail)) {
			display = detail
				.map((item) => (item as { msg?: string })?.msg || "")
				.filter(Boolean)
				.join("; ");
		} else {
			display = error?.message || "请求失败";
		}
		(error as { displayMessage?: string }).displayMessage = display;
		return Promise.reject(error);
	},
);

export default service;
