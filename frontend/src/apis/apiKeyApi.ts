import request from "@/utils/request";
import type { ModelConfig } from "@/utils/interface";

/** 验证 API Key 请求参数 */
export interface ValidateApiKeyRequest {
	api_key: string;
	base_url?: string;
	model_id: string;
	api_type?: string;
}

/** 验证 API Key 响应 */
export interface ValidateApiKeyResponse {
	valid: boolean;
	message: string;
}

/** 保存 API 配置请求参数 */
export interface SaveApiConfigRequest {
	coordinator: {
		apiKey: string;
		baseUrl: string;
		modelId: string;
		apiType: string;
	};
	modeler: {
		apiKey: string;
		baseUrl: string;
		modelId: string;
		apiType: string;
	};
	coder: {
		apiKey: string;
		baseUrl: string;
		modelId: string;
		apiType: string;
	};
	writer: {
		apiKey: string;
		baseUrl: string;
		modelId: string;
		apiType: string;
	};
	openalex_email: string;
	/** 配置方案名（保存到 model_config.toml 时使用） */
	config_name?: string;
	/** 视觉模型配置（图片质量反馈闭环） */
	vision?: {
		enabled: boolean;
		apiKey: string;
		baseUrl: string;
		model: string;
		apiType: string;
		maxTokens: number;
	};
}

/** 验证 OpenAlex Email 请求参数 */
export interface ValidateOpenalexEmailRequest {
	email: string;
}

/** 验证 OpenAlex Email 响应 */
export interface ValidateOpenalexEmailResponse {
	valid: boolean;
	message: string;
}

/**
 * 验证 API Key 是否有效
 * @param params 验证请求参数
 */
export function validateApiKey(params: ValidateApiKeyRequest) {
	return request.post<ValidateApiKeyResponse>("/validate-api-key", params);
}

/**
 * 验证 OpenAlex Email 是否有效
 * @param params 验证请求参数
 */
export function validateOpenalexEmail(params: ValidateOpenalexEmailRequest) {
	return request.post<ValidateOpenalexEmailResponse>(
		"/validate-openalex-email",
		params,
	);
}

/**
 * 保存 API 配置到后端
 * @param params API 配置参数
 */
export function saveApiConfig(params: SaveApiConfigRequest) {
	return request.post<{ success: boolean; message: string }>(
		"/save-api-config",
		params,
	);
}

/**
 * 获取全部持久化的配置方案
 */
export function getModelConfigs() {
	return request.get<{
		configs: Record<
			string,
			{
				coordinator: ModelConfig;
				modeler: ModelConfig;
				coder: ModelConfig;
				writer: ModelConfig;
			}
		>;
		current: string;
	}>("/model-configs");
}

/**
 * 切换当前配置方案
 * @param name 配置方案名
 */
export function switchModelConfig(name: string) {
	return request.post<{ success: boolean; message: string; current: string }>(
		"/model-configs/switch",
		{ name },
	);
}
