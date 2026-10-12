# G.STD.17-CPP 禁止调用kill、TerminateProcess函数直接终止其他进程

- **规则ID**：4adafbc0-641d-468a-a7ce-aaf9c235cbea
- **更新时间**：2025-03-25 19:24:08

---

**【问题级别】**

一般

**【描述】**

调用kill、TerminateProcess等函数直接强行终止其他进程（如kill -SIGKILL，kill -SIGSTOP），会导致被终止的进程中的资源得不到清理。进程终止时，进程特有的资源将由系统自动释放，而其他资源（尤其是不属于进程的系统资源）在程序退出前难以得到有效地清理。



对于进程/线程间通信，应该主动发送一个停止命令，通知对方安全退出。接收到停止命令的进程应尽快完成进程资源和不再使用的系统资源的清理和释放。当发送给对方进程/线程退出信号后，在等待一定时间内如果对方仍然未退出，可以调用kill、TerminateProcess函数强行终止目标进程。

**【正确示例】**

```
正确的做法是通知对方进程停止，在等待一定时间内如果对方仍然未退出，再强行终止目标进程。

if (inFatalStatus) {
    ...
    kill(pid, SIGUSR1);     // 符合：目标进程将SIGUSR1定义为停止命令
    ...
    if (WaitForRemoteProcessExit() == TIME_OUT) {
        kill(pid, SIGKILL); // 目标进程在限定时间内仍然未退出，强行结束目标进程
    }
}

```
**【错误示例】**

```
if (inFatalStatus) {
    ...
    kill(pid, SIGKILL);     // 不符合：直接调用kill强行结束目标进程
}

```
**【修复建议】**

参考规范http://openx.huawei.com/communityWikiDetails?communityId=41&ibid=SPE1000000176&navid=NVI1000004561
