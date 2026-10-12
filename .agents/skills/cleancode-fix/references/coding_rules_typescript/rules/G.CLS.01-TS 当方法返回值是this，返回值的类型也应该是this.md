# G.CLS.01-TS 当方法返回值是this，返回值的类型也应该是this

- **规则ID**：0a949ccc-10bf-4c06-ad53-8d2a64f4e317
- **更新时间**：2026-04-07 04:35:02

---

**【问题级别】**

一般

**【描述】**

方法链是 面向对象编程里一个常见的模式，即方法的返回值还是类本身，可以继续调用下去。如果方法需要返回自身，返回类型应该声明为this，否则会出现获取不到父类的子方法。

**【正确示例】**

```
##### 场景1：this
- 修复示例：返回值和类型都是this

```typescript
class Foo {
  f1(): this {
    return this;
  }
}
class Bar extends Foo {
  f2(): this {
    return this;
  }
}
const bar = new Bar();
bar.f1().f2(); // f1 返回的是 this，也就是根据上下文确定返回的类型，此处是 Bar ，因此不会报错
```

```
**【错误示例】**

```
##### 场景1：this
- 错误示例：返回值是this，类型不是this

```typescript
class Foo {
  f1(): Foo {
    return this;
  }
}
class Bar extends Foo {
  f2(): Bar {
    return this;
  }
}
const bar = new Bar();
bar.f1().f2(); // 提示：类型“Foo”上不存在属性“f2”，原因：虽然 f1 返回的是 this，但是返回类型是 Foo ，Foo而没有 f2 方法，因此会提示错误
```

```
**【修复建议】**

当方法返回值是this，返回值的类型也应该是this。
