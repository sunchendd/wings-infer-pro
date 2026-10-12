# G.FUD.08 将字符串或指针作为函数参数时，在函数体中应检查参数是否为NULL

- **规则ID**：1ce60f75-72ee-4008-b6ef-4d21db2fdecb
- **更新时间**：2026-04-07 04:10:01

---

**【问题级别】**

一般

**【描述】**

跟踪指针变量从声明到使用的全过程，检查代码里潜在的空指针，并给出空指针产生的代码trace

**【正确示例】**

```
```
struct A {
    int b;
};

int main()
{
    struct A * a = 0;
    if (a==null) return;
    a->b = 1;
}
```

```
**【错误示例】**

```
```
struct A {
    int b;
};

int main()
{
    struct A * a = 0;

    a->b = 2;
}
```

```
**【修复建议】**

```

struct A {

    int b;

};



int main()

{

    struct A * a = 0;

    if (a==null) return;

    a->b = 1;

}

```
