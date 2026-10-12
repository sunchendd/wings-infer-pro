# G.MUSIC.2 使用安全工具类SafeReceiverRegister 替换原生的 registerReceiver方法

- **规则ID**：5982940a-fd54-4f20-9d88-f2a35eaac572
- **更新时间**：2025-06-05 04:00:06

---

**【问题级别】**

一般

**【描述】**

使用安全工具类SafeReceiverRegister 替换原生的 registerReceiver方法

**【正确示例】**

```
public void registerReceiver(String action) {
        //可能存在权限不足，无法接受外部广播，或者其他异常。
        context.registerReceiver(mBroadcastReceiver, new IntentFilter(action));
    }

```
**【错误示例】**

```
public void registerReceiver(String action) {
        //使用安全的SafeReceiverRegister，在接收非系统广播时默认要求传入权限，否则使用本地广播。
        SafeReceiverRegister.newBuilder()
            .addAction(action)
            .regPublicNoLifecycle(context, mBroadcastReceiver, Permission.CROSS_PERMISSiON, null);
    }

```
**【修复建议】**

使用SafeReceiverRegister
