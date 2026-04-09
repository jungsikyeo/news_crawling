import * as React from "react"
import { useState, useEffect } from "react"
import * as SelectPrimitive from "@radix-ui/react-select"
import { ChevronDown, Check } from "lucide-react"
import { cn } from "@/lib/utils"

const Select = SelectPrimitive.Root
const SelectValue = SelectPrimitive.Value

/** Resolve a CSS variable like "--card" into its computed value from :root */
function useCssVar(...varNames: string[]) {
  const [values, setValues] = useState<Record<string, string>>({})

  useEffect(() => {
    function update() {
      const s = getComputedStyle(document.documentElement)
      const v: Record<string, string> = {}
      for (const name of varNames) {
        v[name] = s.getPropertyValue(name).trim()
      }
      setValues(v)
    }
    update()
    const obs = new MutationObserver(update)
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] })
    return () => obs.disconnect()
  }, [varNames.join(",")])

  return values
}

const SelectTrigger = React.forwardRef<
  React.ComponentRef<typeof SelectPrimitive.Trigger>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Trigger>
>(({ className, children, ...props }, ref) => (
  <SelectPrimitive.Trigger
    ref={ref}
    className={cn(
      "flex items-center justify-between gap-1 rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--secondary))] px-2 text-sm text-[hsl(var(--foreground))] focus:outline-none focus:ring-2 focus:ring-[hsl(var(--ring))]",
      className,
    )}
    {...props}
  >
    {children}
    <SelectPrimitive.Icon asChild>
      <ChevronDown className="h-3.5 w-3.5 opacity-50 shrink-0" />
    </SelectPrimitive.Icon>
  </SelectPrimitive.Trigger>
))
SelectTrigger.displayName = SelectPrimitive.Trigger.displayName

const SelectContent = React.forwardRef<
  React.ComponentRef<typeof SelectPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Content>
>(({ className, children, position = "popper", ...props }, ref) => {
  const vars = useCssVar("--card", "--foreground", "--border")

  return (
    <SelectPrimitive.Portal>
      <SelectPrimitive.Content
        ref={ref}
        className={cn(
          "relative z-50 min-w-[8rem] overflow-hidden rounded-md shadow-xl",
          position === "popper" && "translate-y-1",
          className,
        )}
        position={position}
        style={{
          backgroundColor: vars["--card"] ? `hsl(${vars["--card"]})` : undefined,
          color: vars["--foreground"] ? `hsl(${vars["--foreground"]})` : undefined,
          border: vars["--border"] ? `1px solid hsl(${vars["--border"]})` : undefined,
        }}
        {...props}
      >
        <SelectPrimitive.Viewport
          className={cn(
            "p-1",
            position === "popper" && "w-full min-w-[var(--radix-select-trigger-width)]",
          )}
        >
          {children}
        </SelectPrimitive.Viewport>
      </SelectPrimitive.Content>
    </SelectPrimitive.Portal>
  )
})
SelectContent.displayName = SelectPrimitive.Content.displayName

const SelectItem = React.forwardRef<
  React.ComponentRef<typeof SelectPrimitive.Item>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Content> & { value: string }
>(({ className, children, ...props }, ref) => {
  const vars = useCssVar("--foreground", "--secondary")

  return (
    <SelectPrimitive.Item
      ref={ref}
      className={cn(
        "relative flex w-full cursor-pointer select-none items-center rounded-sm py-1.5 pl-7 pr-2 text-sm outline-none data-[disabled]:pointer-events-none data-[disabled]:opacity-50 data-[highlighted]:brightness-125",
        className,
      )}
      style={{
        color: vars["--foreground"] ? `hsl(${vars["--foreground"]})` : undefined,
      }}
      onMouseEnter={(e) => {
        if (vars["--secondary"]) {
          (e.currentTarget as HTMLElement).style.backgroundColor = `hsl(${vars["--secondary"]})`
        }
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLElement).style.backgroundColor = ""
      }}
      {...props}
    >
      <span className="absolute left-2 flex h-3.5 w-3.5 items-center justify-center">
        <SelectPrimitive.ItemIndicator>
          <Check className="h-3.5 w-3.5" />
        </SelectPrimitive.ItemIndicator>
      </span>
      <SelectPrimitive.ItemText>{children}</SelectPrimitive.ItemText>
    </SelectPrimitive.Item>
  )
})
SelectItem.displayName = SelectPrimitive.Item.displayName

export { Select, SelectValue, SelectTrigger, SelectContent, SelectItem }
