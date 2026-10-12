# G.TYP.09 不要在数组遍历中对其进行元素的 remove/add 操作

- **规则ID**：df03eb24-23f1-42c2-bd75-6ea264aa3635
- **更新时间**：2025-06-05 04:35:01

---

**【问题级别】**

一般

**【描述】**

在forEach循环中删除、增加元素，会破坏原本的遍历顺序，可能导致意料之外的结果。

**【正确示例】**

```
const myArr = [1, 2];
const tmpArr = [...myArr];
tmpArr.forEach((val, index) => { 
  console.log(val);  // 输出 1, 2
  if (val === 1) {
    myArr.splice(index, 1);
  }
});
console.log(myArr); // [2]

```
**【错误示例】**

```
const myArr = [1, 2]; 
myArr.forEach((val, index) => {
  console.log(val); // 只输出了 1
  if (val === 1) {
    myArr.splice(index, 1);
  }
});

```
**【修复建议】**

不要在数组遍历中进行元素的 remove/add 操作
