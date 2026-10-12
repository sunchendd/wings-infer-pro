# G.TYP.06-TS 不要通过undefined去定义可选成员或参数

- **规则ID**：b7ff246f-7965-413d-91f7-b3baf56543a9
- **更新时间**：2025-06-05 04:35:02

---

**【问题级别】**

提示

**【描述】**

对于可选成员或可选参数，在声明中使用可选符?标识即可替代undefined。对于类型别名，声明时不应该包括undefined，而是在使用类型别名时再联合undefined。

**【正确示例】**

```
// 使用可选参数替代undefined
interface CoffeeOrder {
  sugarCubes: number;
  milk?: Whole|LowFat|HalfHalf;
}
// 使用可选参数替代undefined
function pourCoffee(volume?: Milliliter) {}
// 声明类型别名时不包括undefined
type CoffeeResponse = Latte|Americano;
class CoffeeService {
  // 在使用类型别名时再联合undefined
  getLatte(): CoffeeResponse|undefined {};
}

```
**【错误示例】**

```
// 在可选成员中使用了undefined
interface CoffeeOrder {
  sugarCubes: number;
  milk: Whole|LowFat|HalfHalf|undefined;
}
// 在可选参数中使用了undefined
function pourCoffee(volume: Milliliter|undefined) {}
// 在类型别名声明时使用了undefined
type CoffeeResponse = Latte|Americano|undefined;
class CoffeeService {
  getLatte(): CoffeeResponse {};
}

```
**【修复建议】**

不要通过undefined去定义可选成员或参数
