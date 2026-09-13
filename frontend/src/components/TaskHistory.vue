<script setup lang="ts">
import { getTasks } from "@/apis/commonApi";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { FileText, History, Loader2 } from "lucide-vue-next";
import { ref, watch } from "vue";
import { useRouter } from "vue-router";

// ---- Props & Emits ----

const props = defineProps<{ open: boolean }>();
const emit = defineEmits<(e: "update:open", value: boolean) => void>();

// ---- State ----

interface TaskItem {
	task_id: string;
	created_at: string;
	has_paper: boolean;
}

const router = useRouter();
const tasks = ref<TaskItem[]>([]);
const loading = ref(false);
const loaded = ref(false);
const error = ref(false);

// ---- Methods ----

/** 加载历史任务列表 */
async function loadTasks() {
	loading.value = true;
	error.value = false;
	try {
		const res = await getTasks();
		tasks.value = res.data.tasks ?? [];
	} catch (e) {
		console.error("加载历史任务失败:", e);
		error.value = true;
	} finally {
		loading.value = false;
		loaded.value = true;
	}
}

/** 重试加载 */
function retryLoad() {
	loadTasks();
}

/** 格式化创建时间 */
function formatTime(iso: string): string {
	const date = new Date(iso);
	if (Number.isNaN(date.getTime())) {
		return iso;
	}
	const pad = (n: number) => String(n).padStart(2, "0");
	return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

/** 打开任务页 */
function openTask(taskId: string) {
	emit("update:open", false);
	router.push(`/task/${taskId}`);
}

// ---- Lifecycle ----

// 组件常驻挂载（v-model 控制显隐），onMounted 只在首次挂载执行一次且此时
// open 为 false，会永远跳过加载。改为监听 open，每次打开弹窗都重新拉取。
watch(
	() => props.open,
	(open) => {
		if (open) {
			loadTasks();
		}
	},
);
</script>

<template>
  <Dialog :open="props.open" @update:open="emit('update:open', $event)">
    <DialogContent class="max-w-xl max-h-[70vh] flex flex-col">
      <DialogHeader>
        <DialogTitle>
          <span class="flex items-center gap-2">
            <History class="h-4 w-4" />
            历史任务
          </span>
        </DialogTitle>
      </DialogHeader>

      <div class="relative flex-1 min-h-0 overflow-hidden">
        <div v-if="loading" class="absolute inset-0 flex items-center justify-center text-muted-foreground text-sm">
          <Loader2 class="h-4 w-4 animate-spin mr-2" />
          加载中...
        </div>
        <div
          v-else-if="loaded && tasks.length === 0"
          class="absolute inset-0 flex flex-col items-center justify-center text-muted-foreground text-sm gap-2"
        >
          <History class="h-8 w-8 opacity-40" />
          暂无历史任务，去提交一个吧
        </div>
        <div
          v-else-if="error"
          class="absolute inset-0 flex flex-col items-center justify-center text-muted-foreground text-sm gap-3"
        >
          <History class="h-8 w-8 opacity-40" />
          <span>加载失败，请确认后端服务已启动</span>
          <Button size="sm" variant="outline" class="h-7 text-xs" @click="retryLoad">重试</Button>
        </div>
        <!-- 用浏览器原生滚动替代 ScrollArea：reka-ui ScrollArea 在 shadcn Dialog 内
             若父 flex 高度链不稳可能不可滚。父容器 relative+overflow-hidden，子容器
             absolute inset-0 + overflow-y-auto，高度被父锁定，内容超出必可滚。 -->
        <div v-else class="absolute inset-0 overflow-y-auto pr-1.5">
          <div class="space-y-2 pr-2">
            <div
              v-for="task in tasks"
              :key="task.task_id"
              class="flex items-center justify-between gap-2 border rounded-lg p-3 hover:bg-muted/50 cursor-pointer"
              @click="openTask(task.task_id)"
            >
              <div class="min-w-0">
                <div class="text-sm font-medium truncate">{{ task.task_id }}</div>
                <div class="text-xs text-muted-foreground mt-0.5">
                  {{ formatTime(task.created_at) }}
                </div>
              </div>
              <div class="flex items-center gap-2 shrink-0">
                <span
                  v-if="task.has_paper"
                  class="flex items-center text-xs px-2 py-0.5 rounded bg-green-50 text-green-700 border border-green-200"
                >
                  <FileText class="h-3 w-3 mr-1" />
                  有论文
                </span>
                <span
                  v-else
                  class="text-xs px-2 py-0.5 rounded bg-muted text-muted-foreground"
                >
                  无论文
                </span>
                <Button size="sm" variant="outline" class="h-7 text-xs" @click.stop="openTask(task.task_id)">
                  查看
                </Button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </DialogContent>
  </Dialog>
</template>
