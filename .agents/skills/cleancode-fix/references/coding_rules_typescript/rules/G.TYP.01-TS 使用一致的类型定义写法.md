# G.TYP.01-TS 使用一致的类型定义写法

- **规则ID**：1c735fbc-1f38-4e85-933e-c89ca1483e48
- **更新时间**：2026-04-07 04:35:02

---

**【问题级别】**

提示

**【描述】**

使用TypeScript定义变量的时候，一般都需要指定类型，建议应该使用小写基础类型来保持一致性。

**【正确示例】**

```
##### 场景1：基础类型
- 修复示例：使用小写基础类型来保持一致性
```javascript
// 使用小写类型
const str: string = 'foo';
const bool: boolean = true;
const num: number = 1;
const symb: symbol = Symbol('foo');
const obj: object = {};
```
##### 场景2：函数表达式定义
- 修复示例：定义函数表达式时，使用具体的函数类型来标明
```javascript
// 使用具体的函数类型
const func: () => number = () => 1;
```
##### 场景3：{}类型
- 修复示例：指定具体的类型
```javascript
// 使用具体的类型
interface Person = { name: string }; 
const foo: Person = { name: 'string' };
```

```
**【错误示例】**

```
##### 场景1：基础类型
- 错误示例：基础类型使用的是大写
```javascript
// 使用了大写类型
const str: String = 'foo';
const bool: Boolean = true;
const num: Number = 1;
const symb: Symbol = Symbol('foo');
const obj: Object = {};
```
##### 场景2：函数表达式定义
- 错误示例：定义函数表达式时，使用了Function类型
```javascript
// 使用了Function类型
const func: Function = () => 1;

```
##### 场景3：{}类型
- 错误示例：使用{}类型
```javascript
// 使用了{}类型
const foo: {} = { a: 'string' };
const curly: {} = 1;
```

```
**【修复建议】**

1. 应该使用小写基础类型来保持一致性。



2. 避免使用Function类型，原因如下：



   - Function只要求是函数类型，对类型的限制比较宽泛，没有起到很好的类型检查目的。



   - 当传入class时，虽然满足Function的类型要求，但是调用会失败，因为会在没有new关键字的情况下调用class。



3. 避免使用{}类型，因为它们意味着“任何非空值”，而不是“任何对象类型”的意思。
