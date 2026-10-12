# G.FUD.05 函数要简短

- **规则ID**：8bb4c995-d842-44f3-af56-6c595e4cd076
- **更新时间**：2025-06-05 04:10:03

---

**【问题级别】**

一般

**【描述】**

函数的参数个数不超过5个。

**【正确示例】**

```
##### 场景1：函数的参数个数超过5个
- 修复示例1：

```c
struct PersonInfo {
    char *name;
    uint8_t age;
    char *gender;
    char *address;
    char *phone;
    char *email;
};

// 符合
void ProtectInfo(const struct PersonInfo *info)
{
    ...
}
```

```
**【错误示例】**

```
##### 场景1：函数的参数个数超过5个
- 错误示例：

```c
// 不符合：函数参数过多
void ProtectInfo(char *name, int age, char *gender, char *address, char *phone, char *email)
{
    ...
}
```

```
**【修复建议】**

函数的参数个数不应超过5个，修改方法参考如下：



1. 使用结构体：将多个参数封装成一个结构体，作为函数的参数传递。



2. 重构函数：如果函数参数过多，可能意味着函数功能过于复杂，可以考虑将函数拆分成多个小函数，每个函数只处理部分参数，使函数更加简单易懂。
