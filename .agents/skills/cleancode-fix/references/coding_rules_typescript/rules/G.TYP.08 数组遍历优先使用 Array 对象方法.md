# G.TYP.08 数组遍历优先使用 Array 对象方法

- **规则ID**：c3e52113-4e5e-4bf2-a0fb-b7695b2be95c
- **更新时间**：2025-06-05 04:35:01

---

**【问题级别】**

提示

**【描述】**

对于数组的遍历处理，应该优先使用Array对象方法

**【正确示例】**

```
const numbers = [1, 2, 3, 4, 5];
// 使用for of遍历求和
let sum = 0;
for (const num of numbers) {
  sum += num;
}
// 使用forEach遍历求和
let sum = 0;
numbers.forEach(num => sum += num);
// better: 使用reduce方法实现求和，是更好的方式
const sum = numbers.reduce((total, num) => total + num, 0);
// 依赖已有数组来创建新的数组，可使用forEach遍历，生成一个新数组
const increasedByOne = [];
numbers.forEach(num => increasedByOne.push(num + 1));
// better: 使用map方法是更好的方式
const increasedByOne = numbers.map(num => num + 1);

```
**【错误示例】**

```
const numbers = [1, 2, 3, 4, 5];
let sum = 0;
// 使用for in遍历数组
for (const num in numbers) {
  console.log(num);
  sum += num;
}

```
**【修复建议】**

数组遍历优先使用 Array 对象方法
