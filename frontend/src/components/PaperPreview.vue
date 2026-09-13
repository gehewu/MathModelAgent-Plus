<script setup lang="ts">
import { compilePaper, downloadPaper, getPaper } from "@/apis/filesApi";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { renderMarkdown } from "@/utils/markdown";
import { Download, FileText, Loader2 } from "lucide-vue-next";
import { onBeforeUnmount, onMounted, ref, watch } from "vue";

// ---- Props & Emits ----

const props = defineProps<{
	open: boolean;
	taskId: string;
	/** 任务运行中时轮询刷新 */
	poll: boolean;
}>();
const emit = defineEmits<(e: "update:open", value: boolean) => void>();

// ---- State ----

const content = ref("");
const available = ref<string[]>([]);
const loading = ref(false);
/** PDF 编译中 */
const compiling = ref(false);
/** 编译结果提示（成功/失败原因） */
const compileMsg = ref("");
let timer: ReturnType<typeof setInterval> | null = null;

/** 可下载文件类型的中文名 */
const FILE_LABELS: Record<string, string> = {
	md: "Markdown",
	docx: "Word",
	pdf: "PDF",
	ipynb: "Notebook",
};

// ---- Methods ----

/** 拉取论文内容 */
async function fetchPaper() {
	if (!props.taskId) return;
	loading.value = true;
	try {
		const res = await getPaper(props.taskId);
		content.value = res.data.content ?? "";
		available.value = res.data.available ?? [];
	} catch {
		// 论文尚未生成时忽略
	} finally {
		loading.value = false;
	}
}

/** 下载论文文件 */
async function handleDownload(file: string) {
	try {
		const res = await downloadPaper(props.taskId, file);
		const blob = new Blob([res.data as Blob]);
		const url = URL.createObjectURL(blob);
		const link = document.createElement("a");
		link.href = url;
		link.download = `${props.taskId}.${file === "ipynb" ? "ipynb" : file}`;
		link.click();
		URL.revokeObjectURL(url);
	} catch (error) {
		console.error("下载失败:", error);
	}
}

/** 生成 PDF（pandoc + xelatex 编译，首次可能较慢） */
async function handleCompile() {
	if (compiling.value) return;
	compiling.value = true;
	compileMsg.value = "";
	try {
		const res = await compilePaper(props.taskId);
		compileMsg.value = res.data.message;
		if (res.data.success) {
			await fetchPaper(); // 刷新后「下载 PDF」按钮出现
		}
	} catch (error) {
		console.error("生成 PDF 失败:", error);
		compileMsg.value = "生成 PDF 失败，请稍后重试";
	} finally {
		compiling.value = false;
	}
}

/** 渲染后的 HTML */
const renderedHtml = ref("");

/** 渲染 Markdown 内容 */
async function renderContent() {
	if (content.value) {
		renderedHtml.value = await renderMarkdown(content.value);
	} else {
		renderedHtml.value = "";
	}
}

// ---- Lifecycle ----

onMounted(() => {
	if (props.open) {
		fetchPaper();
	}
});

onBeforeUnmount(() => {
	if (timer) {
		clearInterval(timer);
		timer = null;
	}
});

// 打开时拉取 + 启动轮询（任务运行中论文会持续更新）
watch(
	() => props.open,
	(open) => {
		if (open) {
			fetchPaper();
			if (props.poll) {
				timer = setInterval(fetchPaper, 10000);
			}
		} else if (timer) {
			clearInterval(timer);
			timer = null;
		}
	},
);

watch(content, () => {
	renderContent();
});
</script>

<template>
  <Dialog :open="props.open" @update:open="emit('update:open', $event)">
    <DialogContent class="max-w-3xl max-h-[85vh] flex flex-col overflow-hidden">
      <DialogHeader class="flex-row items-center justify-between">
        <DialogTitle>论文预览</DialogTitle>
        <div class="flex gap-2">
          <Button
            v-if="content && !available.includes('pdf')"
            size="sm"
            class="h-7 text-xs"
            variant="outline"
            :disabled="compiling"
            @click="handleCompile"
          >
            <Loader2 v-if="compiling" class="h-3.5 w-3.5 mr-1 animate-spin" />
            <FileText v-else class="h-3.5 w-3.5 mr-1" />
            {{ compiling ? "生成中..." : "生成 PDF" }}
          </Button>
          <Button
            v-for="file in available"
            :key="file"
            size="sm"
            class="h-7 text-xs"
            variant="secondary"
            @click="handleDownload(file)"
          >
            <Download class="h-3.5 w-3.5 mr-1" />
            下载 {{ FILE_LABELS[file] ?? file }}
          </Button>
        </div>
      </DialogHeader>

      <p
        v-if="compileMsg"
        class="text-xs text-muted-foreground px-1 -mt-1 whitespace-pre-wrap"
      >
        {{ compileMsg }}
      </p>

      <div class="h-[calc(100vh-14rem)] min-h-[50vh] border rounded-lg overflow-hidden">
        <div v-if="loading" class="h-full flex items-center justify-center text-muted-foreground text-sm">
          <Loader2 class="h-4 w-4 animate-spin mr-2" />
          加载中...
        </div>
        <div
          v-else-if="!content"
          class="h-full flex flex-col items-center justify-center text-muted-foreground text-sm gap-2"
        >
          <FileText class="h-8 w-8 opacity-40" />
          论文尚未生成，任务完成后可在此预览与下载
        </div>
        <ScrollArea v-else type="scroll" class="h-full">
          <article
            class="prose prose-sm max-w-none p-5"
            v-html="renderedHtml"
          ></article>
        </ScrollArea>
      </div>
    </DialogContent>
  </Dialog>
</template>
