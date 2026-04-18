import {
  buildTaskSubmitNetworkHint,
  isTaskSubmitCanceledError,
  isTaskSubmitNetworkError,
  isTaskSubmitTimeoutError,
  recoverSubmittedTaskByIdempotency,
  recoverSubmittedTask,
  submitTaskWithRetry,
} from "./taskSubmitRecovery"

export function createTaskSubmitHandler({
  ensureAuthenticated,
  submittingRef,
  errorTextRef,
  successTextRef,
  beginSubmitGuard,
  isActiveSubmit,
  finishSubmitGuard,
  buildSnapshot,
  buildSubmitOnce,
  refreshUser,
  applyUserBalance,
  router,
  recordPath,
  recordLabel,
  onInsufficientCredits,
}) {
  return async function submitTask() {
    if (!ensureAuthenticated()) return
    if (submittingRef.value) return

    const snapshot = buildSnapshot()
    if (!snapshot) {
      return
    }

    const submittedAt = Date.now()
    const { token, signal } = beginSubmitGuard()
    submittingRef.value = true
    errorTextRef.value = ""
    successTextRef.value = ""
    const submitOnce = buildSubmitOnce({ snapshot, submittedAt, signal })

    try {
      const data = await submitTaskWithRetry({
        signal,
        maxAttempts: 4,
        retryDelayMs: 1200,
        submitOnce,
      })
      if (!isActiveSubmit(token)) return

      const status = String(data?.status || "").trim().toLowerCase()
      if (status === "failed") {
        const reason = String(data?.error_message || "").trim()
        errorTextRef.value = reason
          ? `任务 #${data.id} 处理失败：${reason}`
          : `任务 #${data.id} 排队失败，请到${recordLabel}查看失败原因后重试`
        if (!isActiveSubmit(token)) return
        jumpToRecordPage({ router, recordPath, taskId: data.id, refreshUser })
        return
      }

      successTextRef.value = `提交成功，任务 #${data.id} 已进入处理队列`
      applySubmitSnapshot({ data, applyUserBalance })
      if (!isActiveSubmit(token)) return
      jumpToRecordPage({ router, recordPath, taskId: data.id, refreshUser })
    } catch (error) {
      if (isTaskSubmitCanceledError(error) || !isActiveSubmit(token)) {
        return
      }
      if (isTaskSubmitTimeoutError(error) || isTaskSubmitNetworkError(error)) {
        const idempotentTask = await recoverSubmittedTaskByIdempotency({
          userHttp: snapshot.userHttp,
          taskType: snapshot.taskType,
          platform: snapshot.platform,
          sourceFilename: snapshot.sourceFilename,
          idempotencyKey: snapshot.idempotencyKey,
          signal,
        })
        if (!isActiveSubmit(token)) return
        if (idempotentTask?.id) {
          successTextRef.value = `任务已找回：#${idempotentTask.id}，正在跳转记录页`
          applySubmitSnapshot({ data: idempotentTask, applyUserBalance })
          if (!isActiveSubmit(token)) return
          jumpToRecordPage({ router, recordPath, taskId: idempotentTask.id, refreshUser })
          return
        }
        const recoveredTask = await recoverSubmittedTask({
          taskType: snapshot.taskType,
          paperTitle: snapshot.paperTitle,
          authors: snapshot.authors,
          sourceFilename: snapshot.sourceFilename,
          submittedAt,
          attempts: 6,
          retryDelayMs: 1200,
          signal,
        })
        if (!isActiveSubmit(token)) return
        if (recoveredTask?.id) {
          successTextRef.value = `提交响应中断，但任务 #${recoveredTask.id} 已进入处理队列，正在跳转记录页`
          applySubmitSnapshot({ data: recoveredTask, applyUserBalance })
          if (!isActiveSubmit(token)) return
          jumpToRecordPage({ router, recordPath, taskId: recoveredTask.id, refreshUser })
          return
        }
        try {
          const rescueData = await submitTaskWithRetry({
            signal,
            maxAttempts: 6,
            retryDelayMs: 1500,
            submitOnce,
          })
          if (!isActiveSubmit(token)) return
          successTextRef.value = `网络恢复后已补交成功，任务 #${rescueData.id} 已进入处理队列`
          applySubmitSnapshot({ data: rescueData, applyUserBalance })
          if (!isActiveSubmit(token)) return
          jumpToRecordPage({ router, recordPath, taskId: rescueData.id, refreshUser })
          return
        } catch (rescueError) {
          if (isTaskSubmitCanceledError(rescueError) || !isActiveSubmit(token)) {
            return
          }
        }
      }

      const message = String(error?.message || "").trim()
      if (/通用点数不足/.test(message)) {
        onInsufficientCredits?.()
        errorTextRef.value = `${message}，可先通过充值入口补足后再提交`
        return
      }
      if (isTaskSubmitTimeoutError(error)) {
        errorTextRef.value = `提交耗时较长，请稍后到${recordLabel}确认任务是否已创建`
        return
      }
      if (isTaskSubmitNetworkError(error)) {
        errorTextRef.value = await buildTaskSubmitNetworkHint({ signal })
        return
      }
      errorTextRef.value = message || "提交失败，请稍后重试"
    } finally {
      if (isActiveSubmit(token)) {
        submittingRef.value = false
      }
      finishSubmitGuard(token)
    }
  }
}

async function safelyRefreshUser(refreshUser) {
  if (typeof refreshUser !== "function") return
  try {
    await refreshUser()
  } catch (error) {
    console.warn("task_submit_refresh_user_failed", error)
  }
}

function jumpToRecordPage({ router, recordPath, taskId, refreshUser }) {
  void router.push({ path: recordPath, query: { focus: String(taskId), submitted: "1" } })
  void safelyRefreshUser(refreshUser)
}

function applySubmitSnapshot({ data, applyUserBalance }) {
  if (typeof applyUserBalance !== "function" || !data || typeof data !== "object") {
    return
  }
  const balance =
    typeof data.balance_after_fen === "number"
      ? data.balance_after_fen
      : typeof data.balance_after === "number"
        ? data.balance_after
        : null
  if (typeof balance === "number") {
    applyUserBalance(balance)
  }
}
