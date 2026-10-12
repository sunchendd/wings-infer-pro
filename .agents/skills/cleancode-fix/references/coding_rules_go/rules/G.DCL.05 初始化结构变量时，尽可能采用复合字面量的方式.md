# G.DCL.05 初始化结构变量时，尽可能采用复合字面量的方式

- **规则ID**：014d7fad-45cf-47b2-b421-f4265afb28c4
- **更新时间**：2026-04-07 04:20:01

---

**【问题级别】**

一般

**【描述】**

初始化结构体变量时，优先采用复合字面量的方式，并指定字段名称，以提升代码的可读性。应该尽量用每行一个`字段名: 初始化值`的形式，以避免初始化语句过长或造成折行，影响可读性。

**【正确示例】**

```
##### 场景1：初始化结构体时未采用字面量的方式
- 修复示例：

    ```go
    type Stock struct {
        amount int
        name string
        price big.Rat
        original bool
    }

    func New() *Stock {
        // 符合：使用复合字面量的方式，并指定字段名称
        return &Stock {
            amount: 1,
            name: "foo",
            price: *big.NewRat(200, 100), // price is 2.00
            original: true,
        }
    }
    ```
##### 场景2：初始化结构体时没有指定字段名称
- 修复示例：

    ```go
    type Stock struct {
        amount int
        name string
        price big.Rat
        original bool
    }

    func bar() {
        // 符合：使用复合字面量的方式，并指定字段名称
        s := Stock {
            amount: 1,
            name: "foo",
            price: *big.NewRat(200, 100), // price is 2.00
            original: true,
        }
        ...
    }
    ```


```
**【错误示例】**

```
##### 场景1：初始化结构体时未采用字面量的方式
- 错误示例：

    ```go
    type Stock struct {
        amount int
        name string
        price big.Rat
        original bool
    }

    func New() *Stock {
        s := new(Stock)
        // 不符合：在初始化结构变量时，使用下面的单独给指定字段赋值比较累赘，此种方式比较适用于给已构造完成的结构体的特定字段赋值
        s.amount = 1
        s.name = "foo"
        s.price = *big.NewRat(200, 100) // price is 2.00
        s.original = true
        return s
    }
    ```
##### 场景2：初始化结构体时没有指定字段名称
- 错误示例：

    ```go
    type Stock struct {
        amount int
        name string
        price big.Rat
        original bool
    }

    func bar() {
        s := Stock { 1, "foo", *big.NewRat(200, 100), true } // 不符合：没有指定字段名称
        ...
    }
    ```


```
**【修复建议】**

初始化时，尽量使用复合字面量的方式，并指定字段名称，以提升代码的可读性。
