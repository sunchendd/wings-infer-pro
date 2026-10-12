# G.INT.08 表示对象大小的整数值或变量应当使用size_t类型

- **规则ID**：43367d51-10a7-431f-b8b4-5c9a7d85a5d4
- **更新时间**：2026-04-07 04:10:04

---

**【问题级别】**

一般

**【描述】**

表示对象大小的整数值或变量应当使用`size_t`类型。

**【正确示例】**

```
##### 场景1：使用非size_t类型变量接收sizeof、strlen结果。
- 修复示例1：

```c
size_t GoodCase01(const char *str)
{
    size_t len = strlen(str); // 符合：使用size_t类型变量接收strlen函数返回值
    if (len <= MIN_SIZE) {
        return 0;
    }
    /* 保存字符串的值 */
    return len;
}

size_t BadCase02()
{
    size_t len = sizeof(TestStruct); // 符合：使用size_t类型变量接收sizeof结果
    return len;
}
```


```
**【错误示例】**

```
##### 场景1：使用非size_t类型变量接收sizeof、strlen结果。
- 错误示例：

```c
int BadCase01(const char *str)
{
    int len = strlen(str); // 不符合：使用非size_t类型变量接收strlen函数返回值
    if (len <= 0) {
        return 0;
    }
    /* 保存字符串的值 */
    return len;
}

int BadCase02()
{
    int len = sizeof(TestStruct); // 不符合：使用非size_t类型变量接收sizeof结果
    return len;
}
```


```
**【修复建议】**

1. 对表示对象大小的所有整数值使用`size_t`。

2. 如果赋值表达式右值包含`sizeof`，`strlen`，则左值变量需定义为`size_t`类型。
