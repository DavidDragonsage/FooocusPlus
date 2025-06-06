import type { ComfyNodeConstructor, ComfyObjectInfo, NodeMode } from "typings/comfy.js";
import type {
  IWidget,
  SerializedLGraphNode,
  LGraphNode as TLGraphNode,
  LGraphCanvas,
  ContextMenuItem,
  INodeOutputSlot,
  INodeInputSlot,
} from "typings/litegraph.js";
import type { RgthreeBaseServerNodeConstructor, RgthreeBaseVirtualNodeConstructor } from "typings/rgthree.js";

import { ComfyWidgets } from "scripts/widgets.js";
import { SERVICE as KEY_EVENT_SERVICE } from "./services/key_events_services.js";
import { app } from "scripts/app.js";
import { LogLevel, rgthree } from "./rgthree.js";
import { addHelpMenuItem } from "./utils.js";
import { RgthreeHelpDialog } from "rgthree/common/dialog.js";
import {
  importIndividualNodesInnerOnDragDrop,
  importIndividualNodesInnerOnDragOver,
} from "./feature_import_individual_nodes.js";

/**
 * A base node with standard methods, directly extending the LGraphNode.
 * This can be used for ui-nodes and a further base for server nodes.
 */
export abstract class RgthreeBaseNode extends LGraphNode {
  /**
   * Action strings that can be exposed and triggered from other nodes, like Fast Actions Button.
   */
  static exposedActions: string[] = [];

  static override title: string = "__NEED_CLASS_TITLE__";
  static category = "rgthree";
  static _category = "rgthree"; // `category` seems to get reset by comfy, so reset to this after.

  /**
   * The comfyClass is property ComfyUI and extensions may care about, even through it is only for
   * server nodes. RgthreeBaseServerNode below overrides this with the expected value and we just
   * set it here so extensions that are none the wiser don't break on some unchecked string method
   * call on an undefined calue.
   */
  comfyClass: string = "__NEED_COMFY_CLASS__";

  /** Used by the ComfyUI-Manager badge. */
  readonly nickname = "rgthree";
  /** Are we a virtual node? */
  readonly isVirtualNode: boolean = false;
  /** Are we able to be dropped on (if config is enabled too). */
  isDropEnabled = false;
  /** A state member determining if we're currently removed. */
  removed = false;
  /** A state member determining if we're currently "configuring."" */
  configuring = false;
  /** A temporary width value that can be used to ensure compute size operates correctly. */
  _tempWidth = 0;

  /** Private Mode member so we can override the setter/getter and call an `onModeChange`. */
  private mode_: NodeMode;
  /** An internal bool set when `onConstructed` is run. */
  private __constructed__ = false;
  /** The help dialog. */
  private helpDialog: RgthreeHelpDialog | null = null;

  constructor(title = RgthreeBaseNode.title, skipOnConstructedCall = true) {
    super(title);
    if (title == "__NEED_CLASS_TITLE__") {
      throw new Error("RgthreeBaseNode needs overrides.");
    }
    // Ensure these exist since some other extensions will break in their onNodeCreated.
    this.widgets = this.widgets || [];
    this.properties = this.properties || {};

    // Some checks we want to do after we're constructed, looking that data is set correctly and
    // that our base's `onConstructed` was called (if not, set a DEV warning).
    setTimeout(() => {
      // Check we have a comfyClass defined.
      if (this.comfyClass == "__NEED_COMFY_CLASS__") {
        throw new Error("RgthreeBaseNode needs a comfy class override.");
      }
      // Ensure we've called onConstructed before we got here.
      this.checkAndRunOnConstructed();
    });
  }

  private checkAndRunOnConstructed() {
    if (!this.__constructed__) {
      this.onConstructed();
      const [n, v] = rgthree.logger.logParts(
        LogLevel.DEV,
        `[RgthreeBaseNode] Child class did not call onConstructed for "${this.type}.`,
      );
      console[n]?.(...v);
    }
    return this.__constructed__;
  }

  onDragOver(e: DragEvent): boolean {
    if (!this.isDropEnabled) return false;
    return importIndividualNodesInnerOnDragOver(this, e);
  }

  async onDragDrop(e: DragEvent): Promise<boolean> {
    if (!this.isDropEnabled) return false;
    return importIndividualNodesInnerOnDragDrop(this, e);
  }

  /**
   * When a node is finished with construction, we must call this. Failure to do so will result in
   * an error message from the timeout in this base class. This is broken out and becomes the
   * responsibility of the child class because
   */
  onConstructed() {
    if (this.__constructed__) return false;
    // This is kinda a hack, but if this.type is still null, then set it to undefined to match.
    this.type = this.type ?? undefined;
    this.__constructed__ = true;
    rgthree.invokeExtensionsAsync("nodeCreated", this);
    return this.__constructed__;
  }

  override configure(info: SerializedLGraphNode<TLGraphNode>): void {
    this.configuring = true;
    super.configure(info);
    // Fix https://github.com/comfyanonymous/ComfyUI/issues/1448 locally.
    // Can removed when fixed and adopted.
    for (const w of this.widgets || []) {
      w.last_y = w.last_y || 0;
    }
    this.configuring = false;
  }

  /**
   * Override clone for, at the least, deep-copying properties.
   */
  override clone() {
    const cloned = super.clone();
    // This is whild, but LiteGraph clone doesn't deep clone data, so we will. We'll use structured
    // clone, which most browsers in 2022 support, but but we'll check.
    if (cloned.properties && !!window.structuredClone) {
      cloned.properties = structuredClone(cloned.properties);
    }
    return cloned;
  }

  // @ts-ignore - Changing the property to an accessor here seems to work, but ts compiler complains.
  override set mode(mode: NodeMode) {
    if (this.mode_ != mode) {
      const oldMode = this.mode_;
      this.mode_ = mode;
      this.onModeChange(oldMode, mode);
    }
  }
  override get mode() {
    return this.mode_;
  }

  /** When a mode change, we want all connected nodes to match. */
  onModeChange(from: NodeMode, to: NodeMode) {
    // Override
  }

  /**
   * Given a string, do something. At the least, handle any `exposedActions` that may be called and
   * passed into from other nodes, like Fast Actions Button
   */
  async handleAction(action: string) {
    action; // No-op. Should be overridden but OK if not.
  }

  /**
   * Guess this doesn't exist in Litegraph...
   */
  removeWidget(widgetOrSlot?: IWidget | number) {
    if (typeof widgetOrSlot === "number") {
      this.widgets.splice(widgetOrSlot, 1);
    } else if (widgetOrSlot) {
      const index = this.widgets.indexOf(widgetOrSlot);
      if (index > -1) {
        this.widgets.splice(index, 1);
      }
    }
  }

  /**
   * A default version of the logive when a node does not set `getSlotMenuOptions`. This is
   * necessary because child nodes may want to define getSlotMenuOptions but LiteGraph then won't do
   * it's default logic. This bakes it so child nodes can call this instead (and this doesn't set
   * getSlotMenuOptions for all child nodes in case it doesn't exist).
   */
  defaultGetSlotMenuOptions(slot: {
    input?: INodeInputSlot;
    output?: INodeOutputSlot;
  }): ContextMenuItem[] | null {
    const menu_info: ContextMenuItem[] = [];
    if (slot?.output?.links?.length) {
      menu_info.push({ content: "Disconnect Links", slot: slot });
    }
    let inputOrOutput = slot.input || slot.output;
    if (inputOrOutput) {
      if (inputOrOutput.removable) {
        menu_info.push(
          inputOrOutput.locked ? { content: "Cannot remove" } : { content: "Remove Slot", slot },
        );
      }
      if (!inputOrOutput.nameLocked) {
        menu_info.push({ content: "Rename Slot", slot });
      }
    }
    return menu_info;
  }

  override onRemoved(): void {
    super.onRemoved?.();
    this.removed = true;
  }

  static setUp<T extends RgthreeBaseNode>(...args: any[]) {
    // No-op.
  }

  /**
   * A function to provide help text to be overridden.
   */
  getHelp() {
    return "";
  }

  showHelp() {
    const help = this.getHelp() || (this.constructor as any).help;
    if (help) {
      this.helpDialog = new RgthreeHelpDialog(this, help).show();
      this.helpDialog.addEventListener("close", (e) => {
        this.helpDialog = null;
      });
    }
  }

  override onKeyDown(event: KeyboardEvent): void {
    KEY_EVENT_SERVICE.handleKeyDownOrUp(event);
    if (event.key == "?" && !this.helpDialog) {
      this.showHelp();
    }
  }

  override onKeyUp(event: KeyboardEvent): void {
    KEY_EVENT_SERVICE.handleKeyDownOrUp(event);
  }

  override getExtraMenuOptions(canvas: LGraphCanvas, options: ContextMenuItem[]): void {
    // Some other extensions override getExtraMenuOptions on the nodeType as it comes through from
    // the server, so we can call out to that if we don't have our own.
    if (super.getExtraMenuOptions) {
      super.getExtraMenuOptions?.apply(this, [canvas, options]);
    } else if ((this.constructor as any).nodeType?.prototype?.getExtraMenuOptions) {
      (this.constructor as any).nodeType?.prototype?.getExtraMenuOptions?.apply(this, [
        canvas,
        options,
      ]);
    }
    // If we have help content, then add a menu item.
    const help = this.getHelp() || (this.constructor as any).help;
    if (help) {
      addHelpMenuItem(this, help, options);
    }
  }
}

/**
 * A virtual node. Right now, this is just a wrapper for RgthreeBaseNode (which was the initial
 * base virtual node).
 *
 * TODO: Make RgthreeBaseNode private and move all virtual nodes to this class; cleanup
 * RgthreeBaseNode assumptions that its virtual.
 */
export class RgthreeBaseVirtualNode extends RgthreeBaseNode {
  override isVirtualNode = true;

  constructor(title = RgthreeBaseNode.title) {
    super(title, false);
  }

  static override setUp() {
    if (!this.type) {
      throw new Error(`Missing type for RgthreeBaseVirtualNode: ${this.title}`);
    }
    LiteGraph.registerNodeType(this.type, this);
    if (this._category) {
      this.category = this._category;
    }
  }
}

/**
 * A base node with standard methods, extending the LGraphNode.
 * This is somewhat experimental, but if comfyui is going to keep breaking widgets and inputs, it
 * seems safer than NOT overriding.
 */
export class RgthreeBaseServerNode extends RgthreeBaseNode {
  static nodeData: ComfyObjectInfo | null = null;
  static nodeType: ComfyNodeConstructor | null = null;

  // Drop is enabled by default for server nodes.
  override isDropEnabled = true;

  constructor(title: string) {
    super(title, true);
    this.serialize_widgets = true;
    this.setupFromServerNodeData();
    this.onConstructed();
  }

  getWidgets() {
    return ComfyWidgets;
  }

  /**
   * This takes the server data and builds out the inputs, outputs and widgets. It's similar to the
   * ComfyNode constructor in registerNodes in ComfyUI's app.js, but is more stable and thus
   * shouldn't break as often when it modifyies widgets and types.
   */
  async setupFromServerNodeData() {
    const nodeData = (this.constructor as any).nodeData;
    if (!nodeData) {
      throw Error("No node data");
    }

    // Necessary for serialization so Comfy backend can check types.
    // Serialized as `class_type`. See app.js#graphToPrompt
    this.comfyClass = nodeData.name;

    let inputs = nodeData["input"]["required"];
    if (nodeData["input"]["optional"] != undefined) {
      inputs = Object.assign({}, inputs, nodeData["input"]["optional"]);
    }

    const WIDGETS = this.getWidgets();

    const config: { minWidth: number; minHeight: number; widget?: null | { options: any } } = {
      minWidth: 1,
      minHeight: 1,
      widget: null,
    };
    for (const inputName in inputs) {
      const inputData = inputs[inputName];
      const type = inputData[0];
      // If we're forcing the input, just do it now and forget all that widget stuff.
      // This is one of the differences from ComfyNode and provides smoother experience for inputs
      // that are going to remain inputs anyway.
      // Also, it fixes https://github.com/comfyanonymous/ComfyUI/issues/1404 (for rgthree nodes)
      if (inputData[1]?.forceInput) {
        this.addInput(inputName, type);
      } else {
        let widgetCreated = true;
        if (Array.isArray(type)) {
          // Enums
          Object.assign(config, WIDGETS.COMBO(this, inputName, inputData, app) || {});
        } else if (`${type}:${inputName}` in WIDGETS) {
          // Support custom widgets by Type:Name
          Object.assign(
            config,
            WIDGETS[`${type}:${inputName}`]!(this, inputName, inputData, app) || {},
          );
        } else if (type in WIDGETS) {
          // Standard type widgets
          Object.assign(config, WIDGETS[type]!(this, inputName, inputData, app) || {});
        } else {
          // Node connection inputs
          this.addInput(inputName, type);
          widgetCreated = false;
        }

        // Don't actually need this right now, but ported it over from ComfyWidget.
        if (widgetCreated && inputData[1]?.forceInput && config?.widget) {
          if (!config.widget.options) config.widget.options = {};
          config.widget.options.forceInput = inputData[1].forceInput;
        }
        if (widgetCreated && inputData[1]?.defaultInput && config?.widget) {
          if (!config.widget.options) config.widget.options = {};
          config.widget.options.defaultInput = inputData[1].defaultInput;
        }
      }
    }

    for (const o in nodeData["output"]) {
      let output = nodeData["output"][o];
      if (output instanceof Array) output = "COMBO";
      const outputName = nodeData["output_name"][o] || output;
      const outputShape = nodeData["output_is_list"][o]
        ? LiteGraph.GRID_SHAPE
        : LiteGraph.CIRCLE_SHAPE;
      this.addOutput(outputName, output, { shape: outputShape });
    }

    const s = this.computeSize();
    s[0] = Math.max(config.minWidth, s[0] * 1.5);
    s[1] = Math.max(config.minHeight, s[1]);
    this.size = s;
    this.serialize_widgets = true;
  }

  static __registeredForOverride__: boolean = false;
  static registerForOverride(
    comfyClass: ComfyNodeConstructor,
    nodeData: ComfyObjectInfo,
    rgthreeClass: RgthreeBaseServerNodeConstructor,
  ) {
    if (OVERRIDDEN_SERVER_NODES.has(comfyClass)) {
      throw Error(
        `Already have a class to override ${
          comfyClass.type || comfyClass.name || comfyClass.title
        }`,
      );
    }
    OVERRIDDEN_SERVER_NODES.set(comfyClass, rgthreeClass);
    // Mark the rgthreeClass as `__registeredForOverride__` because ComfyUI will repeatedly call
    // this and certain setups will only want to setup once (like adding context menus, etc).
    if (!rgthreeClass.__registeredForOverride__) {
      rgthreeClass.__registeredForOverride__ = true;
      rgthreeClass.nodeType = comfyClass;
      rgthreeClass.nodeData = nodeData;
      rgthreeClass.onRegisteredForOverride(comfyClass, rgthreeClass);
    }
  }

  static onRegisteredForOverride(comfyClass: any, rgthreeClass: any) {
    // To be overridden
  }
}

/**
 * Keeps track of the rgthree-comfy nodes that come from the server (and want to be ComfyNodes) that
 * we override into a own, more flexible and cleaner nodes.
 */
const OVERRIDDEN_SERVER_NODES = new Map<any, any>();

const oldregisterNodeType = LiteGraph.registerNodeType;
/**
 * ComfyUI calls registerNodeType with its ComfyNode, but we don't trust that will remain stable, so
 * we need to identify it, intercept it, and supply our own class for the node.
 */
LiteGraph.registerNodeType = async function (nodeId: string, baseClass: any) {
  const clazz = OVERRIDDEN_SERVER_NODES.get(baseClass) || baseClass;
  if (clazz !== baseClass) {
    const classLabel = clazz.type || clazz.name || clazz.title;
    const [n, v] = rgthree.logger.logParts(
      LogLevel.DEBUG,
      `${nodeId}: replacing default ComfyNode implementation with custom ${classLabel} class.`,
    );
    console[n]?.(...v);
    // Note, we don't currently call our rgthree.invokeExtensionsAsync w/ beforeRegisterNodeDef as
    // this runs right after that. However, this does mean that extensions cannot actually change
    // anything about overriden server rgthree nodes in their beforeRegisterNodeDef (as when comfy
    // calls it, it's for the wrong ComfyNode class). Calling it here, however, would re-run
    // everything causing more issues than not. If we wanted to support beforeRegisterNodeDef then
    // it would mean rewriting ComfyUI's registerNodeDef which, frankly, is not worth it.
  }
  return oldregisterNodeType.call(LiteGraph, nodeId, clazz);
};
