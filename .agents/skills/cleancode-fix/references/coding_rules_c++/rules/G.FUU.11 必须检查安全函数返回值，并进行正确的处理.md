# G.FUU.11 必须检查安全函数返回值，并进行正确的处理

- **规则ID**：bb759b56-8dca-476c-8139-51e60c7ab865
- **更新时间**：2025-03-25 19:23:43

---

**【问题级别】**

严重

**【描述】**

原则上，如果使用了安全函数，需要进行返回值检查。如果返回值表示错误，那么本函数一般情况下应该立即返回，不能继续执行。



安全函数有多个错误返回值，如果安全函数返回失败，在本函数返回前，根据产品具体场景的不同，执行以下一个或多个措施：



记录日志

返回错误

调用abort立即退出程序(参见G.FUU.08 禁用abort函数中的例外场景)

**【正确示例】**

```
bool ParseBuff(unsigned char *destBuff, size_t destMax)
{
    unsigned char *src = ...
    size_t srcLen = ...
    if (destBuff == NULL || destMax == 0) {
        return false; // 返回失败
    }
    errno_t ret = memcpy_s(destBuff, destMax, src, srcLen);
    if (ret != EOK) {
        Log("memcpy_s failed, err = %d
", err);
        return false; // 返回失败
    }
    ...
    return true;
}

```
**【错误示例】**

```
bool ParseBuff(unsigned char *destBuff, size_t destMax)
{
    unsigned char *src = ...
    size_t srcLen = ...
    if (destBuff == NULL || destMax == 0) {
        return false; // 返回失败
    }
    memcpy_s(destBuff, destMax, src, srcLen);  // 可能拷贝失败
    ...
    return true;
}

```
**【修复建议】**

安全函数有多个错误返回值，如果安全函数返回失败，在本函数返回前，根据产品具体场景的不同，执行以下一个或多个措施：



记录日志

返回错误

调用abort立即退出程序(参见G.FUU.08 禁用abort函数中的例外场景)
