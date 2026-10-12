# SecA_PassByValue

- **规则ID**：36394802-1aa3-4fa5-aed5-4146858244dc
- **更新时间**：2026-04-07 04:10:01

---

**【问题级别】**

一般

**【描述】**

查找函数参数的类型太大（默认情况下超过 128 字节）的情况。要避免此缺陷，应该将此类参数作为指针（在 C 中）或作为引用（在 C++ 中）传递

**【正确示例】**

```
```
typedef struct{
    int a[20];
    int b[20];
    int c[20];
}big_another;

void goodtest_1(big_another *ba){}      //OK
```

```
**【错误示例】**

```
```
struct big {
    int a[20];
    int b[20];
    int c[20];
};

// Warning: passing by value, 240 bytes
void badTest(big b) {   
}
```

```
**【修复建议】**

传递指针或者引用

typedef struct {

int x[10];

} T;

int add_up(T p) { // Better is int add_up(T &p)

int i, total = 0;

for (i = 0; i < 11; i++) {

total += p.x[i];

}

return total;

}
