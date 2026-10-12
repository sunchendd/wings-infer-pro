# G.ENU.02-TS 应该显式定义枚举属性值

- **规则ID**：a97d0f7f-fc60-4c44-8d05-d7eae2328ee4
- **更新时间**：2026-04-07 04:35:02

---

**【问题级别】**

一般

**【描述】**

枚举值的默认值是根据定义顺序排序的，如果在后期附加枚举值定义，则很可能破坏原有语义，建议显式定义枚举的值。

 只定义了枚举对象，默认不赋值，当前枚举对象的第一个值从0开始递增。

 枚举对象的成员值递增只会根据当前值的前一个枚举成员是否有值，有值的话后面依次递增，与第一个枚举成员的值无关。

 字符串的枚举值没有值递增。

**【正确示例】**

```
##### 场景1：枚举属性值
- 修复示例：枚举属性值都有赋值

```typescript
enum Direction {
  UP = 0,
  DOWN = 1,
}

enum Status {
  OPEN = 2,
  CLOSE = 3,
}

enum Status2 {
  OPEN = 0,
  CLOSE = 1,
  PENDING = 2,
}

enum Color {
  RED = '1',
  GREEN  = '2',
}
```

```
**【错误示例】**

```
##### 场景1：枚举属性值
- 错误示例：枚举属性值没有赋值

```typescript
enum Direction {
  UP,
  DOWN,
}
// 输出0,1；原因：只定义了枚举对象，枚举成员默认不赋值，当前枚举成员的第一个值从0开始递增
console.log(Direction.UP, Direction.DOWN); 

enum Status {
  OPEN = 2,
  CLOSE,
}
// 输出2,3；原因：默认给OPEN赋值为2，CLOSE的值默认递增
console.log(Status.OPEN, Status.CLOSE); 

enum Status2 {
  OPEN = 2,
  CLOSE = 1,
  PENDING,
}
// 输出2,1,2；原因：枚举对象的成员值递增只会根据当前值的前一个枚举成员是否有值，有值则后面的枚举成员的值依次递增，与第一个枚举成员的值无关
console.log(Status2.OPEN, Status2.CLOSE, Status2.PENDING); 

enum Color {
  RED = '1',
  // 会报错：枚举成员必须要有初始值。原因：字符串的枚举值没有值递增，当前值的前一个枚举成员的值为字符串，若当前的枚举对象成员未赋值将会报错
  GREEN ,
}
```

```
**【修复建议】**

应该显式定义枚举属性值。
