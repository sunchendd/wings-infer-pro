# G.OBJ.05 禁止在对象实例上直接使用 hasOwnProperty、isPrototypeOf、propertyIsEnumerable方法

- **规则ID**：494fd817-df21-47c6-a4a4-f9aed9cf7e7a
- **更新时间**：2026-04-07 04:35:02

---

**【问题级别】**

一般

**【描述】**

对象实例可以具有属性，这些属性可以将 Object.prototype 的内建函数隐藏，可能导致意外行为或拒绝服务安全漏洞。例如，web 服务器解析来自客户机的 JSON 输入并直接在结果对象上调用 hasOwnProperty 是不安全的，因为恶意客户机可能发送一个JSON值，如 { hasOwnProperty: 1 }，并导致服务器崩溃。因此，禁止在对象实例上直接使用 hasOwnProperty、isPrototypeOf、propertyIsEnumerable方法。

**【正确示例】**

```
##### 场景1：hasOwnProperty、isPrototypeOf、propertyIsEnumerable方法
- 修复示例：使用对象原型调用hasOwnProperty、isPrototypeOf、propertyIsEnumerable方法。

```javascript
const hasBarProperty = Object.prototype.hasOwnProperty.call(foo, 'bar');

const isPrototypeOfBar = Object.prototype.isPrototypeOf.call(foo, bar);

const barIsEnumerable = Object.prototype.propertyIsEnumerable.call(foo, 'bar');

```

```
**【错误示例】**

```
##### 场景1：hasOwnProperty、isPrototypeOf、propertyIsEnumerable方法
- 错误示例：直接使用对象实例调用hasOwnProperty、isPrototypeOf、propertyIsEnumerable方法。

```javascript
const hasBarProperty = foo.hasOwnProperty('bar');

const isPrototypeOfBar = foo.isPrototypeOf(bar);

const barIsEnumerable = foo.propertyIsEnumerable('bar');

```

```
**【修复建议】**

不在对象实例上直接使用 hasOwnProperty、isPrototypeOf、propertyIsEnumerable方法，使用Object.prototype.hasOwnProperty.call，Object.prototype.isPrototypeOf.call，Object.prototype.propertyIsEnumerable.call来代替。
