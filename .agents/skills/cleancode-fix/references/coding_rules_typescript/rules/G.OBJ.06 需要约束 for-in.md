# G.OBJ.06 需要约束 for-in

- **规则ID**：769d3f0b-f712-4d34-a828-55ad64a44efe
- **更新时间**：2026-04-07 04:35:02

---

**【问题级别】**

一般

**【描述】**

在使用 for-in 遍历对象时，会把从原型链继承来的属性也包括进来。这样会导致意想不到的项出现。

**【正确示例】**

```
##### 场景1：for-in
- 修复示例1：在 for-in 循环中使用hasOwnProperty来排除不需要的原型属性。

```javascript
for (const key in student) {
  if (Object.prototype.hasOwnProperty.call(student, key)) {
    console.log(key);
  }
}

for (const key in student) {
  if ({}.hasOwnProperty.call(student, key)) {
    console.log(key);
  }
}

```
- 修复示例2：使用Object.keys()来遍历。
```javascript
// 更好的方式
Object.keys(student).forEach(key => console.log(key))
```

```
**【错误示例】**

```
##### 场景1：for-in
- 错误示例：使用 for-in 遍历对象，导致对象中的原型属性也被输出。

```javascript
// 重写Object.bind方法
Object.prototype.bind = function() {}  

const student = {
  name: 'Lilei',
  age: 18,
};

for (const key in student) {
  // 打印name、age、bind，其中bind并不是预期属性，有可能导致代码出错
  console.log(key);
}

```

```
**【修复建议】**

应该在 for-in 循环中使用Object.prototype.hasOwnProperty来排除不需要的原型属性。也可以使用Object.keys()替代for-in进行遍历。
