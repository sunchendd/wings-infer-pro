# G.EXP.15-CPP 避免使用reinterpret_cast

- **规则ID**：74d73d87-096f-46e6-b6f4-c60c9b992183
- **更新时间**：2025-03-25 19:22:23

---

**【问题级别】**

一般

**【描述】**

reinterpret_cast用于转换不相关类型。尝试用reinterpret_cast将一种类型强制转换另一种类型，这破坏了类型的安全性与可靠性，是一种不安全的转换。不同类型之间尽量避免转换。

**【正确示例】**

```
##### 场景1：不同类型之间的指针强转
- 修复示例：重构代码，考虑使用相同类型。
```c
class B { ... };

void Foo(B* b)
{
    ... // 符合
}
```
##### 场景2：从基类到派生类的转换
- 修复示例：
```c
class A { ... };
class B : public A { ... };

void Foo(A* a)
{
    B* b = dynamic_cast<B *>(a);  // 符合：继承体系下行转换适合用`dynamic_cast`而不是`reinterpret_cast`
}
```

```
**【错误示例】**

```
##### 场景1：不同类型之间的指针强转
- 错误示例：
```c
class A { ... };
class B { ... };

void Foo(A* a)
{
    B* b = reinterpret_cast<B *>(a);  // 不符合
}
```
##### 场景2：从基类到派生类的转换
- 错误示例：
```c
class A { ... };
class B : public A { ... };

void Foo(A* a)
{
    B* b = reinterpret_cast<B *>(a);  // 不符合
}
```

```
**【修复建议】**

避免使用reinterpret_cast
