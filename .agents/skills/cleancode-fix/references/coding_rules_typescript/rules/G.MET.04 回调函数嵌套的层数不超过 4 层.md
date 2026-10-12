# G.MET.04 回调函数嵌套的层数不超过 4 层

- **规则ID**：e33b6248-e5a7-4c23-a94e-2ab9e42877fc
- **更新时间**：2026-04-07 04:35:01

---

**【问题级别】**

提示

**【描述】**

很多 JavaScript 类库是使用回调模式处理异步操作。一个最常见的隐患就是嵌套的回调，代码嵌套层级越深越难以阅读。

**【正确示例】**

```
##### 场景1：回调函数嵌套的层数
- 修复示例：把匿名函数改成函数声明

```javascript
foo1(handleFoo1);
function handleFoo1() {
  foo2(handleFoo2);
}
function handleFoo2() {
  foo3(handleFoo3);
}
function handleFoo3() {
  foo4(handleFoo4);
}
function handleFoo4() {
  foo5(handleFoo5);
}
function handleFoo5() {
  foo6();
}
```

```
**【错误示例】**

```
##### 场景1：回调函数嵌套的层数
- 错误示例：回调函数嵌套的层数超过 4 层

```javascript
foo1(function() { // 嵌套1层
  foo2(function() { // 嵌套2层
    foo3(function() { // 嵌套3层
      foo4(function() { // 嵌套4层
        foo5(function() { // 嵌套5层
          ...
        });
       });
    });
  });
});
```

```
**【修复建议】**

回调函数嵌套的层数不超过 4 层。
