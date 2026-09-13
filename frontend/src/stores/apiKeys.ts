import { getModelConfigs, switchModelConfig } from "@/apis/apiKeyApi";
import { AgentType } from "@/utils/enum";
import type { ModelConfig } from "@/utils/interface";
import { defineStore } from "pinia";
import { computed, ref } from "vue";

/** API Key 和模型配置 Store */
export const useApiKeyStore = defineStore(
	"apiKeys",
	() => {
		// ---- State ----

		/** 协调者模型配置 */
		const coordinatorConfig = ref<ModelConfig>({
			apiKey: "",
			baseUrl: "",
			modelId: "",
			apiType: "",
			contextWindow: 128000,
		});

		/** 建模者模型配置 */
		const modelerConfig = ref<ModelConfig>({
			apiKey: "",
			baseUrl: "",
			modelId: "",
			apiType: "",
			contextWindow: 128000,
		});

		/** 编码者模型配置 */
		const coderConfig = ref<ModelConfig>({
			apiKey: "",
			baseUrl: "",
			modelId: "",
			apiType: "",
			contextWindow: 128000,
		});

		/** 写作者模型配置 */
		const writerConfig = ref<ModelConfig>({
			apiKey: "",
			baseUrl: "",
			modelId: "",
			apiType: "",
			contextWindow: 128000,
		});

		/** OpenAlex 邮箱 */
		const openalexEmail = ref<string>("");

		/** 全部持久化配置方案名 */
		const configNames = ref<string[]>([]);

		/** 当前选中的配置方案名 */
		const currentConfigName = ref<string>("config1");

		/** 视觉模型配置（图片质量反馈闭环） */
		const visionConfig = ref<{
			enabled: boolean;
			apiKey: string;
			baseUrl: string;
			model: string;
			apiType: string;
			maxTokens: number;
		}>({
			enabled: false,
			apiKey: "",
			baseUrl: "",
			model: "",
			apiType: "openai-chat",
			maxTokens: 400,
		});

		// ---- Getters ----

		/** 判断所有配置是否为空 */
		const isEmpty = computed(() => {
			return Object.values(getAllAgentConfigs()).every(
				(config) => config.apiKey === "",
			);
		});

		// ---- Actions ----

		/** 设置协调者模型配置 */
		function setCoordinatorConfig(config: ModelConfig) {
			coordinatorConfig.value = { ...config };
		}

		/** 设置建模者模型配置 */
		function setModelerConfig(config: ModelConfig) {
			modelerConfig.value = { ...config };
		}

		/** 设置编码者模型配置 */
		function setCoderConfig(config: ModelConfig) {
			coderConfig.value = { ...config };
		}

		/** 设置写作者模型配置 */
		function setWriterConfig(config: ModelConfig) {
			writerConfig.value = { ...config };
		}

		/** 设置 OpenAlex 邮箱 */
		function setOpenalexEmail(email: string) {
			console.log("setOpenalexEmail", email);
			openalexEmail.value = email;
		}

		/** 设置视觉模型配置 */
		function setVisionConfig(config: typeof visionConfig.value) {
			visionConfig.value = { ...config };
		}

		/** 加载全部配置方案列表 */
		async function loadModelConfigs() {
			try {
				const res = await getModelConfigs();
				configNames.value = Object.keys(res.data.configs ?? {});
				if (res.data.current) {
					currentConfigName.value = res.data.current;
				}
			} catch (error) {
				console.error("加载配置方案失败:", error);
			}
		}

		/** 切换当前配置方案 */
		async function switchConfig(name: string) {
			try {
				const res = await switchModelConfig(name);
				currentConfigName.value = res.data.current;
				return { success: true, message: res.data.message };
			} catch (error) {
				console.error("切换配置方案失败:", error);
				return { success: false, message: "切换失败" };
			}
		}

		/**
		 * 把指定配置方案的 Agent 配置合并进 store 各字段。
		 * 用于切换方案后刷新表单：后端 config 段只含部分字段，缺失字段保留原值，避免覆盖。
		 */
		async function loadConfigIntoStore(name: string) {
			try {
				const res = await getModelConfigs();
				const cfg = res.data.configs?.[name];
				if (!cfg) return;
				setCoordinatorConfig({ ...coordinatorConfig.value, ...cfg.coordinator });
				setModelerConfig({ ...modelerConfig.value, ...cfg.modeler });
				setCoderConfig({ ...coderConfig.value, ...cfg.coder });
				setWriterConfig({ ...writerConfig.value, ...cfg.writer });
			} catch (error) {
				console.error("加载配置方案到表单失败:", error);
			}
		}

		/** 获取所有 Agent 的模型配置 */
		function getAllAgentConfigs() {
			return {
				[AgentType.COORDINATOR]: coordinatorConfig.value,
				[AgentType.MODELER]: modelerConfig.value,
				[AgentType.CODER]: coderConfig.value,
				[AgentType.WRITER]: writerConfig.value,
			};
		}

		/** 重置所有配置为默认值 */
		function resetAll() {
			coordinatorConfig.value = {
				apiKey: "",
				baseUrl: "",
				modelId: "",
				apiType: "",
				contextWindow: 128000,
			};
			modelerConfig.value = {
				apiKey: "",
				baseUrl: "",
				modelId: "",
				apiType: "",
				contextWindow: 128000,
			};
			coderConfig.value = {
				apiKey: "",
				baseUrl: "",
				modelId: "",
				apiType: "",
				contextWindow: 128000,
			};
			writerConfig.value = {
				apiKey: "",
				baseUrl: "",
				modelId: "",
				apiType: "",
				contextWindow: 128000,
			};
			openalexEmail.value = "";
			visionConfig.value = {
				enabled: false,
				apiKey: "",
				baseUrl: "",
				model: "",
				apiType: "openai-chat",
				maxTokens: 400,
			};
		}

		return {
			// 状态
			coordinatorConfig,
			modelerConfig,
			coderConfig,
			writerConfig,
			openalexEmail,
			isEmpty,
			configNames,
			currentConfigName,
			visionConfig,

			// 方法
			setCoordinatorConfig,
			setModelerConfig,
			setCoderConfig,
			setWriterConfig,
			setOpenalexEmail,
			setVisionConfig,
			getAllAgentConfigs,
			resetAll,
			loadModelConfigs,
			loadConfigIntoStore,
			switchConfig,
		};
	},
	{
		persist: true, // 启用持久化存储
	},
);
