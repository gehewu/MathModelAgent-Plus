<script setup lang="ts">
import {
	saveApiConfig,
	validateApiKey,
	validateOpenalexEmail,
} from "@/apis/apiKeyApi";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
	Select,
	SelectContent,
	SelectGroup,
	SelectItem,
	SelectLabel,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import { useApiKeyStore } from "@/stores/apiKeys";
import { getErrorMessage } from "@/utils/request";
import { CheckCircle, XCircle } from "lucide-vue-next";
import { computed, ref, watch } from "vue";

// ---- Props & Emits ----

const props = defineProps<{ open: boolean }>();
const emit = defineEmits<(e: "update:open", value: boolean) => void>();
const { toast } = useToast();

// ---- Reactive State ----

const apiKeyStore = useApiKeyStore();

/** API 类型选项 */
const apiTypeOptions = [
	{ value: "openai-chat", label: "OpenAI Chat" },
	{ value: "openai-responses", label: "OpenAI Responses" },
	{ value: "anthropic", label: "Anthropic" },
];

/** Agent 表单配置 */
interface AgentFormConfig {
	apiKey: string;
	baseUrl: string;
	modelId: string;
	apiType: string;
	contextWindow: number;
}

/** 本地表单数据 */
const form = ref<{
	coordinator: AgentFormConfig;
	modeler: AgentFormConfig;
	coder: AgentFormConfig;
	writer: AgentFormConfig;
	openalex_email: string;
	vision: {
		enabled: boolean;
		apiKey: string;
		baseUrl: string;
		model: string;
		apiType: string;
		maxTokens: number;
	};
}>({
	coordinator: {
		apiKey: "",
		baseUrl: "",
		modelId: "",
		apiType: "",
		contextWindow: 128000,
	},
	modeler: {
		apiKey: "",
		baseUrl: "",
		modelId: "",
		apiType: "",
		contextWindow: 128000,
	},
	coder: {
		apiKey: "",
		baseUrl: "",
		modelId: "",
		apiType: "",
		contextWindow: 128000,
	},
	writer: {
		apiKey: "",
		baseUrl: "",
		modelId: "",
		apiType: "",
		contextWindow: 128000,
	},
	openalex_email: "",
	vision: {
		enabled: false,
		apiKey: "",
		baseUrl: "",
		model: "",
		apiType: "openai-chat",
		maxTokens: 400,
	},
});

/** 验证加载状态 */
const validating = ref(false);

/** 当前选中的已有配置方案 */
const selectedConfigName = ref<string>("");

/** 新配置方案名（输入后保存时创建） */
const newConfigName = ref<string>("");

/** 各配置项的验证结果 */
const validationResults = ref({
	coordinator: { valid: false, message: "" },
	modeler: { valid: false, message: "" },
	coder: { valid: false, message: "" },
	writer: { valid: false, message: "" },
	openalex_email: { valid: false, message: "" },
});

// ---- Computed ----

/** 判断所有验证是否都通过 */
const allValid = computed(() => {
	return Object.values(validationResults.value).every((result) => result.valid);
});

/** 模型配置列表 */
const modelConfigs = computed(() => [
	{ key: "coordinator", label: "协调者模型配置" },
	{ key: "modeler", label: "建模手模型配置" },
	{ key: "coder", label: "代码手模型配置" },
	{ key: "writer", label: "论文手模型配置" },
]);

// ---- Methods ----

/** 从 store 加载数据到表单 */
const loadFromStore = () => {
	form.value.coordinator = { ...apiKeyStore.coordinatorConfig };
	form.value.modeler = { ...apiKeyStore.modelerConfig };
	form.value.coder = { ...apiKeyStore.coderConfig };
	form.value.writer = { ...apiKeyStore.writerConfig };
	form.value.openalex_email = apiKeyStore.openalexEmail;
	form.value.vision = { ...apiKeyStore.visionConfig };
};

/** 保存表单数据到 store 和后端 */
const saveToStore = async () => {
	apiKeyStore.setCoordinatorConfig(form.value.coordinator);
	apiKeyStore.setModelerConfig(form.value.modeler);
	apiKeyStore.setCoderConfig(form.value.coder);
	apiKeyStore.setWriterConfig(form.value.writer);
	apiKeyStore.setOpenalexEmail(form.value.openalex_email);
	apiKeyStore.setVisionConfig(form.value.vision);
	const configName = newConfigName.value.trim() || selectedConfigName.value;
	try {
		await saveApiConfig({
			coordinator: form.value.coordinator,
			modeler: form.value.modeler,
			coder: form.value.coder,
			writer: form.value.writer,
			openalex_email: form.value.openalex_email,
			config_name: configName || undefined,
			vision: form.value.vision,
		});
		// 保存成功后刷新配置方案列表
		await apiKeyStore.loadModelConfigs();
	} catch (error) {
		console.error("保存配置到后端失败:", error);
		toast({
			title: "保存配置失败",
			description: getErrorMessage(error),
			variant: "destructive",
		});
	}
};

/** 切换到选中的配置方案 */
const switchToSelected = async () => {
	if (!selectedConfigName.value) return;
	const result = await apiKeyStore.switchConfig(selectedConfigName.value);
	if (result.success) {
		newConfigName.value = "";
		await apiKeyStore.loadModelConfigs();
		// 把切到的方案配置加载进表单，避免表单仍显示旧方案、误点"保存"覆盖
		await apiKeyStore.loadConfigIntoStore(selectedConfigName.value);
		loadFromStore();
	}
};

// ---- Lifecycle Hooks ----

// 组件常驻挂载（v-model 控制显隐），onMounted 只在首次挂载执行一次，
// 后端未就绪/首次加载失败后不会重试。改为监听 open，每次打开弹窗都重新拉取配置列表。
watch(
	() => props.open,
	(open) => {
		if (open) {
			loadFromStore();
			loadModelConfigs();
		}
	},
);

/** 加载配置方案列表并同步当前选中项 */
const loadModelConfigs = async () => {
	await apiKeyStore.loadModelConfigs();
	selectedConfigName.value = apiKeyStore.currentConfigName;
};

// ---- Methods (continued) ----

/** 更新弹窗开关状态 */
const updateOpen = (value: boolean) => {
	emit("update:open", value);
};

/** 保存并关闭弹窗 */
const saveAndClose = async () => {
	await saveToStore();
	updateOpen(false);
};

/** 验证大模型 API Key */
const validateModelApiKey = async (config: {
	apiKey: string;
	baseUrl: string;
	modelId: string;
	apiType: string;
}) => {
	if (!config.apiKey) {
		return { valid: false, message: "API Key 为空" };
	}

	if (!config.modelId) {
		return { valid: false, message: "Model ID 为空" };
	}

	try {
		const result = await validateApiKey({
			api_key: config.apiKey,
			base_url: config.baseUrl || "https://api.openai.com/v1",
			model_id: config.modelId,
			api_type: config.apiType || "openai-chat",
		});

		return {
			valid: result.data.valid,
			message: result.data.message,
		};
	} catch (error) {
		return {
			valid: false,
			message: "✗ 验证失败: 无法连接到验证服务",
		};
	}
};

/** 一键验证所有 API Keys */
const validateAllApiKeys = async () => {
	validating.value = true;

	validationResults.value = {
		coordinator: { valid: false, message: "" },
		modeler: { valid: false, message: "" },
		coder: { valid: false, message: "" },
		writer: { valid: false, message: "" },
		openalex_email: { valid: false, message: "" },
	};

	try {
		for (const config of modelConfigs.value) {
			const key = config.key as keyof typeof validationResults.value;
			const formKey = config.key as keyof typeof form.value;

			validationResults.value[key] = { valid: false, message: "验证中..." };
			validationResults.value[key] = await validateModelApiKey(
				form.value[formKey] as {
					apiKey: string;
					baseUrl: string;
					modelId: string;
					apiType: string;
				},
			);

			await new Promise((resolve) => setTimeout(resolve, 1000));
		}

		validationResults.value.openalex_email = await validateOpenalexEmail({
			email: form.value.openalex_email,
		}).then((res) => res.data);
	} catch (error) {
		console.error("验证过程中发生错误:", error);
		for (const key of Object.keys(validationResults.value)) {
			if (
				!validationResults.value[key as keyof typeof validationResults.value]
					.message
			) {
				validationResults.value[key as keyof typeof validationResults.value] = {
					valid: false,
					message: "验证过程中发生未知错误",
				};
			}
		}
	} finally {
		validating.value = false;
	}
};

/** 重置所有表单数据 */
const resetAll = () => {
	form.value = {
		coordinator: {
			apiKey: "",
			baseUrl: "",
			modelId: "",
			apiType: "",
			contextWindow: 128000,
		},
		modeler: {
			apiKey: "",
			baseUrl: "",
			modelId: "",
			apiType: "",
			contextWindow: 128000,
		},
		coder: {
			apiKey: "",
			baseUrl: "",
			modelId: "",
			apiType: "",
			contextWindow: 128000,
		},
		writer: {
			apiKey: "",
			baseUrl: "",
			modelId: "",
			apiType: "",
			contextWindow: 128000,
		},
		openalex_email: "",
		vision: {
			enabled: false,
			apiKey: "",
			baseUrl: "",
			model: "",
			apiType: "openai-chat",
			maxTokens: 400,
		},
	};
};
</script>

<template>
  <Dialog :open="props.open" @update:open="updateOpen">
    <DialogContent class="max-w-xl max-h-[85vh] overflow-y-auto">
      <DialogHeader>
        <DialogTitle>设置</DialogTitle>
        <DialogDescription>
          为每个 Agent 配置 API 类型和模型
        </DialogDescription>
      </DialogHeader>

      <div class="space-y-4 py-2">

        <!-- 配置方案管理 -->
        <div class="space-y-2 border rounded-lg p-3 bg-muted/30">
          <h3 class="text-sm font-medium">配置方案（可保存多套，后端持久化）</h3>
          <div class="flex gap-2 items-end">
            <div class="flex-1 space-y-1">
              <Label class="text-xs text-muted-foreground">已有方案</Label>
              <Select v-model="selectedConfigName">
                <SelectTrigger class="w-full h-7 text-xs">
                  <SelectValue placeholder="选择配置方案" />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectItem v-for="name in apiKeyStore.configNames" :key="name" :value="name">
                      {{ name }}
                    </SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>
            </div>
            <Button @click="switchToSelected" class="h-7 text-xs px-3" variant="secondary">
              切换
            </Button>
          </div>
          <div class="space-y-1">
            <Label class="text-xs text-muted-foreground">新方案名（保存时创建，留空则保存到选中方案）</Label>
            <Input v-model.trim="newConfigName" placeholder="如: config2 / deepseek-家庭" class="h-7 text-xs" />
          </div>
        </div>

        <!-- Models Configurations -->
        <div v-for="config in modelConfigs" :key="config.key" class="space-y-2">
          <h3 class="text-sm font-medium">{{ config.label }}</h3>
          <div class="grid grid-cols-2 gap-2">
            <div class="space-y-1">
              <Label :for="`${config.key}-api-type`" class="text-xs text-muted-foreground">API 类型</Label>
              <Select :model-value="(form as any)[config.key].apiType"
                @update:model-value="(value: any) => { (form as any)[config.key].apiType = value }">
                <SelectTrigger class="w-full h-7 text-xs">
                  <SelectValue placeholder="选择 API 类型" />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectLabel>API 类型</SelectLabel>
                    <SelectItem v-for="opt in apiTypeOptions" :key="opt.value" :value="opt.value">
                      {{ opt.label }}
                    </SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>
            </div>

            <div class="space-y-1">
              <Label :for="`${config.key}-api-key`" class="text-xs text-muted-foreground">API Key</Label>
              <Input :id="`${config.key}-api-key`" v-model.trim="(form as any)[config.key].apiKey" type="password"
                placeholder="请输入 API Key" class="h-7 text-xs flex-1" />
              <div v-if="validationResults[config.key as keyof typeof validationResults].message"
                class="flex items-center">
                <CheckCircle v-if="validationResults[config.key as keyof typeof validationResults].valid"
                  class="h-4 w-4 text-green-500" />
                <XCircle v-else class="h-4 w-4 text-red-500" />
              </div>
            </div>
          </div>

          <div class="grid grid-cols-2 gap-2">
            <div class="space-y-1">
              <Label :for="`${config.key}-base-url`" class="text-xs text-muted-foreground">Base URL</Label>
              <Input :id="`${config.key}-base-url`" v-model.trim="(form as any)[config.key].baseUrl"
                placeholder="https://api.openai.com/v1" class="h-7 text-xs" />
            </div>
            <div class="space-y-1">
              <Label :for="`${config.key}-model-id`" class="text-xs text-muted-foreground">Model ID</Label>
              <Input :id="`${config.key}-model-id`" v-model.trim="(form as any)[config.key].modelId"
                placeholder="gpt-4o / claude-sonnet-4-20250514" class="h-7 text-xs" />
            </div>
          </div>
          <div class="space-y-1">
            <Label :for="`${config.key}-context-window`" class="text-xs text-muted-foreground">
              上下文窗口（token）
            </Label>
            <Input :id="`${config.key}-context-window`"
              v-model.number="(form as any)[config.key].contextWindow" type="number"
              placeholder="128000" class="h-7 text-xs" min="4096" step="1024" />
          </div>
          <div v-if="validationResults[config.key as keyof typeof validationResults].message" :class="[
            'text-xs px-2 py-1 rounded text-left border',
            validationResults[config.key as keyof typeof validationResults].valid ? 'bg-green-50 text-green-700 border-green-200' : 'bg-red-50 text-red-700 border-red-200'
          ]">
            {{ validationResults[config.key as keyof typeof validationResults].message }}
          </div>
        </div>
      </div>

      <!-- 视觉模型配置 -->
      <div class="space-y-2 border rounded-lg p-3">
        <div class="flex items-center justify-between">
          <h3 class="text-sm font-medium">视觉模型（图片质量反馈）</h3>
          <label class="flex items-center gap-1.5 text-xs">
            <input v-model="form.vision.enabled" type="checkbox" class="accent-primary" />
            启用
          </label>
        </div>
        <div class="text-xs text-muted-foreground">
          启用后 Coder 画图会经视觉模型评估并迭代重绘，需支持视觉的 OpenAI 兼容模型
        </div>
        <div class="grid grid-cols-2 gap-2">
          <div class="space-y-1">
            <Label class="text-xs text-muted-foreground">API Key</Label>
            <Input v-model.trim="form.vision.apiKey" type="password" placeholder="请输入视觉模型 API Key" class="h-7 text-xs" />
          </div>
          <div class="space-y-1">
            <Label class="text-xs text-muted-foreground">Base URL</Label>
            <Input v-model.trim="form.vision.baseUrl" placeholder="https://api.siliconflow.cn/v1" class="h-7 text-xs" />
          </div>
        </div>
        <div class="space-y-1">
          <Label class="text-xs text-muted-foreground">模型名称</Label>
          <Input v-model.trim="form.vision.model" placeholder="Qwen/Qwen3-Omni-30B-A3B-Captioner" class="h-7 text-xs" />
        </div>
      </div>

      <div class="space-y-2">
        <h3 class="text-sm font-medium">其他</h3>
        <Label :for="`openalex-email`" class="text-xs text-muted-foreground">OpenAlex Email</Label>
        <div class="text-xs text-muted-foreground">
          使用 email 注册账号从 <a href="https://openalex.org/" target="_blank"
            class="text-blue-600 hover:text-blue-800 underline text-xs">OpenAlex</a> 获取访问文献权利
        </div>
        <Input :id="`openalex-email`" v-model.trim="form.openalex_email" placeholder="请输入 OpenAlex Email"
          class="h-7 text-xs flex-1" />
        <div v-if="validationResults.openalex_email.message" :class="[
          'text-xs px-2 py-1 rounded text-left border',
          validationResults.openalex_email.valid ? 'bg-green-50 text-green-700 border-green-200' : 'bg-red-50 text-red-700 border-red-200'
        ]">
          {{ validationResults.openalex_email.message }}
        </div>
      </div>

      <div class="flex justify-between items-center pt-3 border-t">
        <div class="flex justify-between items-center gap-2">
          <Button @click="validateAllApiKeys" :disabled="validating" class="h-7 text-xs px-3" variant="secondary">
            {{ validating ? '验证中...' : '一键验证' }}
          </Button>
          <Button @click="resetAll" class="h-7 text-xs px-3" variant="secondary">
            重置
          </Button>
        </div>
        <div class="flex space-x-2">
          <Button variant="outline" @click="updateOpen(false)" class="h-7 text-xs px-3">
            取消
          </Button>
          <Button @click="saveAndClose" class="h-7 text-xs px-3">
            保存
          </Button>
        </div>
      </div>
    </DialogContent>
  </Dialog>
</template>
