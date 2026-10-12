# 安全TOP问题-查找代码尝试覆盖基类/父类中的方法，但由于方法签名不一致而未发生覆盖的很多情况

- **规则ID**：73e6119d-8589-4b00-9a27-04e6ca730846
- **更新时间**：2025-03-25 19:23:31

---

**【问题级别】**

严重

**【描述】**

可查找代码尝试覆盖基类/父类中的方法，但由于方法签名不一致而未发生覆盖的很多情况。例如，它可查找由于缺少const修饰符而覆盖虚函数（这会导致类型签名不一致）方面的很多缺陷。



**【正确示例】**

```
```cpp
class Base {
    virtual void foo() const
    {
        /*...*/
    }
};
class Derive : public Base {
    void foo() const override
    { 
        /* ... */ 
    }
};
```


```
**【错误示例】**

```
- 缺少const导致子类无法覆盖父类函数
```cpp
class Base {
    virtual const char* foo() const
    {
        /*...*/
        return nullptr;
    }
};
class Derive : public Base {
	// true_negative SecBrella:SecA_BadOverride
    const char* foo()
    { 
        /* ... */ 
        return nullptr;
    }
};
```


```
**【修复建议】**

确保父类中的成员函数，不存在非static的同名函数，同时遵守 G.CLS.12-CPP 在重写虚函数时应明确指定override或final 规则。
