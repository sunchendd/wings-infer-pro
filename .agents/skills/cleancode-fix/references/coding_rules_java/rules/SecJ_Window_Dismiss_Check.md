# SecJ_Window_Dismiss_Check

- **规则ID**：798df44f-4392-406d-be27-af51812ed1dd
- **更新时间**：2026-04-07 04:00:02

---

**【问题级别】**

一般

**【描述】**

在调用系统的dismiss()方法前，没有对状态进行判断，导致抛出NullPointerException异常。

**【正确示例】**

```
```java

public void test01Bad(Context mContext, PopupWindow popupWindow) {

if (mContext != null && !((Activity) mContext).isFinishing()) {

// 【GOOD】在调用系统的dismiss()方法前，进行判空

if (popupWindow != null) {

popupWindow.dismiss();

}

}

}



public void test02Bad(Context mContext, PopupWindow popupWindow, PopupWindow otherPopupWindow) {

if (mContext != null && !((Activity) mContext).isFinishing() && popupWindow.isShowing()) {

// 【GOOD】在调用系统的dismiss()方法前，进行判空

if (otherPopupWindow!= null) {

otherPopupWindow.dismiss();

}

}

}

```

```
**【错误示例】**

```
```java

public void test01Bad(Context mContext, PopupWindow popupWindow) {

if (mContext != null && !((Activity) mContext).isFinishing()) {

// 【不符合】在调用系统的dismiss()方法前，没有对状态进行判断，导致抛出NullPointerException异常

popupWindow.dismiss();

}

}



public void test02Bad(Context mContext, PopupWindow popupWindow, PopupWindow otherPopupWindow) {

if (mContext != null && !((Activity) mContext).isFinishing() && popupWindow.isShowing()) {

// 【不符合】在调用系统的dismiss()方法前，没有对状态进行判断，导致抛出NullPointerException异常

otherPopupWindow.dismiss();

}

}

```

```
**【修复建议】**

在调用系统的dismiss()方法前，提前进行判空检查。
