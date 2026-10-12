# SecA_CBG_ArrayStaticIndex

- **规则ID**：8be42383-a04b-4019-9951-c5371fd59e25
- **更新时间**：2026-04-07 04:10:01

---

**【问题级别】**

一般

**【描述】**

由于静态变量如果不进行重新赋值则会保持上一次的值不变，当静态变量用做数组下标时，如果不进行校验就可能因前一次的值超出范围导致数组越界。

**【正确示例】**

```
```
static const int G_IMAGE_ION_SIZE6 = 3;
const int SIZE = 10;
const int MAX = 185;
void StaticVariablesAsArraySubscriptsGoodCase09()
{
    int gImageSizes[SIZE];
    /* POTENTIAL FLAW GOOD:  静态常量不告警 */
    gImageSizes[G_IMAGE_ION_SIZE6] = MAX;
}
```

```
**【错误示例】**

```
```
static int g_index = 10;

/*
* @scene: 数组的静态下标在使用前未校验
*/
void StaticVariablesAsArraySubscriptsBadCase()
{
    int arr[9] = {0};
    // POTENTIAL FLAW: g_index为静态变量
    int c = arr[g_index];
}
```

```
**【修复建议】**

无符号数只校验上限，有符号数要校验上下限；
