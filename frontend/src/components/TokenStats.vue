<script setup lang="ts">
import { getTrack } from "@/apis/commonApi";
import { Button } from "@/components/ui/button";
import { Fuel, X } from "lucide-vue-next";
import { onBeforeUnmount, onMounted, ref } from "vue";

// ---- Props ----

/** 任务 ID */
interface AgentUsage {
	prompt_tokens: number;
	completion_tokens: number;
	total_tokens: number;
	chat_count: number;
	cost: number;
}

const props = defineProps<{ taskId: string }>();

// ---- State ----

const totalTokens = ref(0);
const totalCost = ref(0);
const agents = ref<Record<string, AgentUsage>>({});
const open = ref(false);
let timer: ReturnType<typeof setInterval> | null = null;

// ---- Methods ----

/** 格式化 token 数（千分位缩写） */
const formatTokens = (n: number) =>
	n >= 1000 ? `${(n / 1000).toFixed(1)}k` : `${n}`;

/** 格式化费用 */
const formatCost = (n: number) => `¥${n.toFixed(4)}`;

/** 拉取统计 */
async function fetchStats() {
	try {
		const res = await getTrack(props.taskId);
		totalTokens.value = res.data.total_tokens ?? 0;
		totalCost.value = res.data.total_cost ?? 0;
		agents.value = res.data.agents ?? {};
	} catch {
		// 任务未开始或接口未就绪时静默忽略
	}
}

// ---- Lifecycle ----

onMounted(() => {
	fetchStats();
	timer = setInterval(fetchStats, 10000);
});

onBeforeUnmount(() => {
	if (timer) {
		clearInterval(timer);
		timer = null;
	}
});
</script>

<template>
  <div class="relative">
    <Button variant="outline" size="sm" class="h-8 text-xs" @click="open = !open">
      <Fuel class="h-3.5 w-3.5 mr-1" />
      {{ formatTokens(totalTokens) }} tokens · {{ formatCost(totalCost) }}
    </Button>
    <div
      v-if="open"
      class="absolute right-0 top-9 z-50 w-72 rounded-lg border bg-background shadow-lg p-3"
    >
      <div class="flex justify-between items-center mb-2">
        <span class="text-sm font-medium">Token 用量统计</span>
        <X class="h-4 w-4 cursor-pointer" @click="open = false" />
      </div>
      <div v-if="Object.keys(agents).length === 0" class="text-xs text-muted-foreground">
        暂无统计（任务运行后每 10 秒自动更新）
      </div>
      <table v-else class="w-full text-xs">
        <thead>
          <tr class="text-muted-foreground">
            <th class="text-left font-normal">Agent</th>
            <th class="text-right font-normal">tokens</th>
            <th class="text-right font-normal">次数</th>
            <th class="text-right font-normal">费用</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(usage, name) in agents" :key="name">
            <td class="py-0.5">{{ name }}</td>
            <td class="text-right">{{ formatTokens(usage.total_tokens) }}</td>
            <td class="text-right">{{ usage.chat_count }}</td>
            <td class="text-right">{{ formatCost(usage.cost) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
