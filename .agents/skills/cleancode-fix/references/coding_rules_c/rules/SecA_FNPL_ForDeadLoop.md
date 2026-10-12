# SecA_FNPL_ForDeadLoop

- **规则ID**：0f265d43-a344-4645-917c-b4e88b5da635
- **更新时间**：2026-04-07 04:10:01

---

**【问题级别】**

一般

**【描述】**

for循环中循环变量每次进行的偏移量需要校验有效性

**【正确示例】**

```
```
int FNPL_ForDeadLoop_GoodCase01(const int arr[], int arrLen)
{
    int sum = 0;
    int maxArrSize = arrLen < MAX_NUM ? arrLen : MAX_NUM;
    /* 符合 */
    for (int i = 0; i < maxArrSize; i += 1) {
        sum += arr[i];
    }
    return sum;
}
```

```
**【错误示例】**

```
```
int FNPL_ForDeadLoop_BadCase01(int offset, const int arr[], int arrLen)
{
    int sum = 0;
    int maxArrSize = arrLen < MAX_NUM ? arrLen : MAX_NUM;
    /* 不符合:偏移量未校验  offset如果是负数，这里就是死循环  */
    for (int i = 0; i < maxArrSize; i += offset) {
        sum += arr[i];
    }
    return sum;
}
```

```
**【修复建议】**

1.识别并保存循环变量

    2.识别判断语句，保存已判断的变量

    3.识别++ --语句，如果语句L是循环变量，R是未判断的变量，则报告警【Example】
