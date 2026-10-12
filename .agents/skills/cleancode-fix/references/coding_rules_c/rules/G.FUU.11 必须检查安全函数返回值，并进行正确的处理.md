# G.FUU.11 必须检查安全函数返回值，并进行正确的处理

- **规则ID**：b0d54bf5-81c9-4093-a99a-cd3e9cf9f85e
- **更新时间**：2026-04-07 04:10:02

---

**【问题级别】**

严重

**【描述】**

必须检查安全函数返回值，并进行正确的处理。安全函数包括memset_s类，memcpy_s类，printf_s类，strnCpy类，strCpy类。

**【正确示例】**

```
##### 场景1：未对memcpy_s的返回值进行校验
- 修复示例：

```c
bool ParseBuff(unsigned char *destBuff, size_t destMax)
{
    unsigned char *src = ...
    size_t srcLen = ...
    if (destBuff == NULL || destMax == 0) {
        return false; // 返回失败
    }
    errno_t ret = memcpy_s(destBuff, destMax, src, srcLen); // 符合：增加返回值校验
    if (ret != EOK) {
        Log("memcpy_s failed, ret = %d
", ret);
        return false; // 返回失败
    }
    ...
    return true;
}
```
##### 场景2：未对memset_s的返回值进行校验
- 修复示例：
```c
bool GoodCase2(char *destBuff, size_t destMax, size_t count)
{
    if (destBuff == NULL || destMax == 0 || count == 0) {
        return false; // 返回失败
    }
    // 符合：对安全函数的返回值进行校验
    errno_t rc = memset_s(destBuff, destMax, 0, count);
    if (rc != EOK) {
        return false;
    }
    return true;
}
```


```
**【错误示例】**

```
##### 场景1：未对memcpy_s的返回值进行校验
- 错误示例：
```c
bool ParseBuff(unsigned char *destBuff, size_t destMax)
{
    unsigned char *src = ...
    size_t srcLen = ...
    if (destBuff == NULL || destMax == 0) {
        return false; // 返回失败
    }
    memcpy_s(destBuff, destMax, src, srcLen); // 不符合：未校验安全函数返回值
    ...
    return true;
}
```
##### 场景2：未对memset_s的返回值进行校验
- 错误示例：
```c
bool BadCase02(char *destBuff, size_t destMax, size_t count)
{
    if (destBuff == NULL || destMax == 0 || count == 0) {
        return false; // 返回失败
    }

    // 不符合：未检查安全函数返回值
    memset_s(destBuff, destMax, 0, count);

    return true;
}
```


```
**【修复建议】**

对安全函数的返回值进行校验。
