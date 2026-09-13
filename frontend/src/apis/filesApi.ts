import request from "@/utils/request";

/**
 * 获取任务工作区文件列表
 * @param task_id 任务ID
 */
export function getFiles(task_id: string) {
	return request.get<{
		files: {
			filename: string;
			file_type: string;
		}[];
	}>("/files", {
		params: { task_id },
	});
}

/**
 * 获取单个文件下载链接
 * @param task_id 任务ID
 * @param filename 文件名
 */
export async function getFileDownloadUrl(task_id: string, filename: string) {
	return await request.get<{ download_url: string }>("/download_url", {
		params: {
			task_id,
			filename,
		},
	});
}

/**
 * 获取所有文件压缩包下载链接
 * @param task_id 任务ID
 */
export async function getAllFilesDownloadUrl(task_id: string) {
	return await request.get<{ download_url: string }>("/download_all_url", {
		params: {
			task_id,
		},
	});
}

/**
 * 获取任务论文内容（res.md）及可下载文件清单
 * @param task_id 任务ID
 */
export function getPaper(task_id: string) {
	return request.get<{ content: string; available: string[] }>(
		`/paper/${task_id}`,
	);
}

/**
 * 下载论文文件（md / docx / ipynb）
 * @param task_id 任务ID
 * @param file 文件类型
 */
export function downloadPaper(task_id: string, file: string) {
	return request.get(`/paper/${task_id}/download`, {
		params: { file },
		responseType: "blob",
	});
}
