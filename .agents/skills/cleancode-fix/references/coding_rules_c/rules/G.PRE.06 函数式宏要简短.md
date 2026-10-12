# G.PRE.06 函数式宏要简短

- **规则ID**：63a24542-7cc7-450d-95c0-d3cf679cbec3
- **更新时间**：2026-04-07 04:10:02

---

**【问题级别】**

一般

**【描述】**

函数式宏不超过10行(非空非注释)。

**【正确示例】**

```
##### 场景1：函数式宏超过10行
- 修复示例：

```cpp
// 符合
void BubbleSort(int arr[], int n)
{
    int i, j;
    for (i = 0; i < n - 1; i++) {
        for (j = 0; j < n - i - 1; j++) {
            if (arr[j] > arr[j + 1]) {
                int temp = arr[j];
                arr[j] = arr[j + 1];
                arr[j + 1] = temp;
            }
        }
    }
}
```

```
**【错误示例】**

```
##### 场景1：函数式宏超过10行
- 错误示例：

```cpp
// 不符合，函数式宏超过十行
#define BUBBLESORT(arr, n)                \
    int i, j;                             \
    for (i = 0; i < n - 1; i++) {         \
        for (j = 0; j < n - i - 1; j++) { \
            if (arr[j] > arr[j + 1]) {    \
                int temp = arr[j];        \
                arr[j] = arr[j + 1];      \
                arr[j + 1] = temp;        \
            }                             \
        }                                 \
    }
```

```
**【修复建议】**

如果函数式宏超过10行，建议使用函数代替，请参考[G.PRE.01 使用函数代替函数式宏]。
